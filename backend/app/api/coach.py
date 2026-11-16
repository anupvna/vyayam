"""Coach chat: ask, see history, apply a proposed change, clear the conversation.

Providers come from settings (Groq, then Gemini, for whichever keys are set). Tests and
the evaluation set app.state.coach_providers instead, so they never touch the network.
"""

import json
from datetime import date, datetime
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.coach import context
from app.coach.actions import Action, apply, check
from app.coach.providers import Gemini, Groq, Provider
from app.coach.service import RateLimited, check_rate, converse
from app.config import get_settings

router = APIRouter(prefix="/coach", tags=["coach"])


def providers(request: Request) -> list[Provider]:
    override = getattr(request.app.state, "coach_providers", None)
    if override is not None:
        return override
    s = get_settings()
    chain: list[Provider] = []
    if s.groq_api_key:
        chain.append(Groq(s.groq_api_key, s.groq_model, s.coach_timeout_seconds))
    if s.gemini_api_key:
        chain.append(Gemini(s.gemini_api_key, s.gemini_model, s.coach_timeout_seconds))
    return chain


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    today: date

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Type a message")
        return v


class ActionOut(BaseModel):
    index: int
    type: str
    label: str
    applied: bool


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "coach"]
    text: str
    actions: list[ActionOut]
    source: str | None
    created_at: datetime


class StatusOut(BaseModel):
    ai: bool  # False: engine-only answers (no provider configured)


class ApplyIn(BaseModel):
    today: date


class ApplyOut(BaseModel):
    message: str
    minutes: int | None = None  # for shorten_today: the Today screen applies it


def _out(r: asyncpg.Record) -> MessageOut:
    stored = r["actions"] if isinstance(r["actions"], list) else json.loads(r["actions"])
    return MessageOut(
        id=r["id"],
        role=r["role"],
        text=r["content"],
        actions=[
            ActionOut(index=i, type=a["type"], label=a["label"], applied=a.get("applied", False))
            for i, a in enumerate(stored)
        ],
        source=r["source"],
        created_at=r["created_at"],
    )


@router.get("/status", response_model=StatusOut)
async def coach_status(request: Request, user: CurrentUser = Depends(current_user)) -> StatusOut:
    return StatusOut(ai=bool(providers(request)))


@router.get("/messages", response_model=list[MessageOut])
async def list_messages(
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[MessageOut]:
    rows = await conn.fetch(
        """SELECT * FROM (SELECT * FROM coach_messages WHERE user_id = $1
           ORDER BY created_at DESC, id DESC LIMIT 60) recent ORDER BY created_at, id""",
        user.id,
    )
    return [_out(r) for r in rows]


@router.post("/messages", response_model=list[MessageOut])
async def ask(
    body: AskIn,
    request: Request,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[MessageOut]:
    s = get_settings()
    try:
        await check_rate(conn, user, s.coach_messages_per_10_min, s.coach_messages_per_day)
    except RateLimited as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e)) from e

    outcome = await converse(conn, user, body.text, body.today, providers(request))
    stored = [
        {**c.action.model_dump(), "label": c.label, "applied": False} for c in outcome.actions
    ]
    await conn.execute(
        """INSERT INTO coach_messages (user_id, role, content, actions, source)
           VALUES ($1, 'coach', $2, $3::jsonb, $4)""",
        user.id,
        outcome.text,
        json.dumps(stored),
        outcome.source,
    )
    rows = await conn.fetch(
        """SELECT * FROM coach_messages WHERE user_id = $1
           ORDER BY created_at DESC, id DESC LIMIT 2""",
        user.id,
    )
    return [_out(r) for r in reversed(rows)]


@router.post("/messages/{message_id}/actions/{index}", response_model=ApplyOut)
async def apply_action(
    message_id: UUID,
    index: int,
    body: ApplyIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> ApplyOut:
    row = await conn.fetchrow(
        "SELECT actions FROM coach_messages WHERE id = $1 AND user_id = $2 AND role = 'coach'",
        message_id,
        user.id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    stored = row["actions"] if isinstance(row["actions"], list) else json.loads(row["actions"])
    if not 0 <= index < len(stored):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such suggestion")
    if stored[index].get("applied"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already done")

    action = Action.model_validate({k: stored[index].get(k) for k in Action.model_fields})
    ctx = await context.build(conn, user, body.today)
    checked = check(action, ctx)  # again: the plan may have changed since the reply
    if not checked.ok:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Can't do that now: {checked.reason}.")
    async with conn.transaction():
        view = await apply(action, conn, user, ctx)
        stored[index]["applied"] = True
        await conn.execute(
            "UPDATE coach_messages SET actions = $1::jsonb WHERE id = $2",
            json.dumps(stored),
            message_id,
        )
    return ApplyOut(message=f"Done: {checked.label}.", minutes=view.get("minutes"))


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute("DELETE FROM coach_messages WHERE user_id = $1", user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
