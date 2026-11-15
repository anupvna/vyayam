"""Profile: the onboarding answers, plus goal guardrails.

Every query is filtered by the logged-in user's id, so one user can never read or
change another's profile.
"""

from dataclasses import asdict
from datetime import date
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.catalog import BODY_PART_IDS
from app.engine.goals import assess_goal, bmi

router = APIRouter(prefix="/profile", tags=["profile"])

MIN_AGE, MAX_AGE = 18, 90

Sex = Literal["male", "female"]
Experience = Literal["beginner", "intermediate", "advanced"]
Goal = Literal["fat_loss", "muscle_gain", "recomposition", "strength"]


class GoalFields(BaseModel):
    """The fields needed to assess a goal (shared by save and preview)."""

    model_config = ConfigDict(extra="forbid")

    sex: Sex
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    goal: Goal
    target_weight_kg: float | None = Field(default=None, ge=30, le=300)
    target_body_fat_pct: float | None = Field(default=None, ge=3, le=50)
    unit_system: Literal["metric", "imperial"] = "metric"  # used to phrase the advice


class ProfileIn(GoalFields):
    birth_year: int
    experience: Experience
    training_days: list[int] = Field(min_length=1, max_length=6)
    session_minutes: int = Field(ge=20, le=180)
    injury_areas: list[str] = Field(default_factory=list)
    injury_notes: str = Field(default="", max_length=500)

    @field_validator("birth_year")
    @classmethod
    def _adult(cls, v: int) -> int:
        age = date.today().year - v
        if not MIN_AGE <= age <= MAX_AGE:
            raise ValueError(f"Vyayam is for adults aged {MIN_AGE}-{MAX_AGE}")
        return v

    @field_validator("training_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days must be 0 (Mon) to 6 (Sun)")
        if len(set(v)) != len(v):
            raise ValueError("days must not repeat")
        return sorted(v)

    @field_validator("injury_areas")
    @classmethod
    def _body_parts(cls, v: list[str]) -> list[str]:
        unknown = set(v) - BODY_PART_IDS
        if unknown:
            raise ValueError(f"unknown body parts: {sorted(unknown)}")
        return sorted(set(v))

    @field_validator("injury_notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class AdviceOut(BaseModel):
    code: str
    level: str
    message: str


class ProfileOut(ProfileIn):
    model_config = ConfigDict(extra="ignore")

    age: int
    bmi: float
    advice: list[AdviceOut]


def _advice(p: GoalFields) -> list[AdviceOut]:
    found = assess_goal(
        sex=p.sex,
        height_cm=p.height_cm,
        weight_kg=p.weight_kg,
        goal=p.goal,
        target_weight_kg=p.target_weight_kg,
        target_body_fat_pct=p.target_body_fat_pct,
        units=p.unit_system,
    )
    return [AdviceOut(**asdict(a)) for a in found]


def _to_out(row: asyncpg.Record) -> ProfileOut:
    data = dict(row)
    p = ProfileIn.model_validate({k: data[k] for k in ProfileIn.model_fields})
    return ProfileOut(
        **p.model_dump(),
        age=date.today().year - p.birth_year,
        bmi=round(bmi(p.weight_kg, p.height_cm), 1),
        advice=_advice(p),
    )


_COLUMNS = list(ProfileIn.model_fields)


@router.get("", response_model=ProfileOut)
async def get_profile(
    user: CurrentUser = Depends(current_user), conn: asyncpg.Connection = Depends(get_conn)
) -> ProfileOut:
    row = await conn.fetchrow(
        f"SELECT {', '.join(_COLUMNS)} FROM profiles WHERE user_id = $1", user.id
    )
    if row is None:
        # 404 tells the app "not onboarded yet".
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile yet")
    return _to_out(row)


@router.put("", response_model=ProfileOut)
async def save_profile(
    body: ProfileIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> ProfileOut:
    values = body.model_dump()
    cols = ", ".join(_COLUMNS)
    params = ", ".join(f"${i}" for i in range(2, len(_COLUMNS) + 2))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS)
    # Column names come from our own model, never from user input, so the f-string is safe;
    # all values are passed as parameters.
    row = await conn.fetchrow(
        f"""
        INSERT INTO profiles (user_id, {cols}) VALUES ($1, {params})
        ON CONFLICT (user_id) DO UPDATE SET {updates}, updated_at = now()
        RETURNING {cols}
        """,
        user.id,
        *(values[c] for c in _COLUMNS),
    )
    return _to_out(row)


@router.post("/assess", response_model=list[AdviceOut])
async def preview_advice(
    body: GoalFields, _user: CurrentUser = Depends(current_user)
) -> list[AdviceOut]:
    """Live goal check for the onboarding screen, before anything is saved."""
    return _advice(body)
