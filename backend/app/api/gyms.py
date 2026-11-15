"""Gyms: named sets of equipment. Exactly one is active at a time.

Ownership rule used everywhere: every query includes `user_id = <current user>`.
Asking for someone else's gym returns 404, the same as a gym that doesn't exist, so
the API never even confirms that another user's gym exists.
"""

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.catalog import EQUIPMENT_IDS

router = APIRouter(prefix="/gyms", tags=["gyms"])

MAX_GYMS = 10
_FIELDS = "id, name, equipment, is_active"


class GymIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    equipment: list[str] = Field(default_factory=list, max_length=len(EQUIPMENT_IDS))

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("equipment")
    @classmethod
    def _equipment(cls, v: list[str]) -> list[str]:
        unknown = set(v) - EQUIPMENT_IDS
        if unknown:
            raise ValueError(f"unknown equipment: {sorted(unknown)}")
        return sorted(set(v))


class GymOut(BaseModel):
    id: UUID
    name: str
    equipment: list[str]
    is_active: bool


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")


@router.get("", response_model=list[GymOut])
async def list_gyms(
    user: CurrentUser = Depends(current_user), conn: asyncpg.Connection = Depends(get_conn)
) -> list[GymOut]:
    rows = await conn.fetch(
        f"SELECT {_FIELDS} FROM gyms WHERE user_id = $1 ORDER BY created_at, id", user.id
    )
    return [GymOut(**dict(r)) for r in rows]


@router.post("", response_model=GymOut, status_code=status.HTTP_201_CREATED)
async def create_gym(
    body: GymIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> GymOut:
    async with conn.transaction():
        count = await conn.fetchval("SELECT count(*) FROM gyms WHERE user_id = $1", user.id)
        if count >= MAX_GYMS:
            raise HTTPException(status.HTTP_409_CONFLICT, f"You can save up to {MAX_GYMS} gyms")
        row = await conn.fetchrow(
            f"""
            INSERT INTO gyms (user_id, name, equipment, is_active)
            VALUES ($1, $2, $3, $4) RETURNING {_FIELDS}
            """,
            user.id,
            body.name,
            body.equipment,
            count == 0,  # your first gym becomes the active one
        )
    return GymOut(**dict(row))


@router.put("/{gym_id}", response_model=GymOut)
async def update_gym(
    gym_id: UUID,
    body: GymIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> GymOut:
    row = await conn.fetchrow(
        f"""
        UPDATE gyms SET name = $3, equipment = $4, updated_at = now()
        WHERE id = $1 AND user_id = $2 RETURNING {_FIELDS}
        """,
        gym_id,
        user.id,
        body.name,
        body.equipment,
    )
    if row is None:
        raise _not_found()
    return GymOut(**dict(row))


@router.post("/{gym_id}/activate", response_model=GymOut)
async def activate_gym(
    gym_id: UUID,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> GymOut:
    async with conn.transaction():
        exists = await conn.fetchval(
            "SELECT 1 FROM gyms WHERE id = $1 AND user_id = $2", gym_id, user.id
        )
        if not exists:
            raise _not_found()
        # Deactivate first: the unique index allows only one active gym per user.
        await conn.execute(
            "UPDATE gyms SET is_active = false WHERE user_id = $1 AND is_active", user.id
        )
        row = await conn.fetchrow(
            f"UPDATE gyms SET is_active = true WHERE id = $1 AND user_id = $2 RETURNING {_FIELDS}",
            gym_id,
            user.id,
        )
    return GymOut(**dict(row))


@router.delete("/{gym_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gym(
    gym_id: UUID,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    async with conn.transaction():
        was_active = await conn.fetchval(
            "DELETE FROM gyms WHERE id = $1 AND user_id = $2 RETURNING is_active",
            gym_id,
            user.id,
        )
        if was_active is None:
            raise _not_found()
        if was_active:
            # Keep exactly one active gym: promote the most recently created one left.
            await conn.execute(
                """
                UPDATE gyms SET is_active = true
                WHERE id = (SELECT id FROM gyms WHERE user_id = $1
                            ORDER BY created_at DESC, id DESC LIMIT 1)
                """,
                user.id,
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
