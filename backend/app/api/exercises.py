"""Exercise library endpoints: browse, details with alternatives, favorite/hide.

Everything is personalised to the logged-in user: "available" uses their active
gym's equipment, "safe" uses their injury areas, and alternatives respect their
favorites and hidden exercises.
"""

from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.engine.alternatives import find_alternatives, is_available, is_safe
from app.library import Exercise, load_library

router = APIRouter(prefix="/exercises", tags=["exercises"])

Preference = Literal["favorite", "hidden", "none"]


class ExerciseSummary(BaseModel):
    id: str
    name: str
    pattern: str
    kind: str
    primary: list[str]
    secondary: list[str]
    equipment: list[list[str]]
    difficulty: int
    unilateral: bool
    available: bool  # you have the equipment at your active gym
    safe: bool  # doesn't load an area you marked as injured
    preference: Preference


class ExerciseDetail(ExerciseSummary):
    loads: list[str]
    injury_conflicts: list[str]  # loaded areas that you marked as injured
    setup: list[str]
    execution: list[str]
    breathing: str
    mistakes: list[str]
    safety: str
    alternatives: list[ExerciseSummary]


class Context:
    """What we know about the user that affects exercise choices."""

    def __init__(self, equipment: frozenset[str], injured: frozenset[str], prefs: dict[str, str]):
        self.equipment = equipment
        self.injured = injured
        self.prefs = prefs

    @property
    def favorites(self) -> frozenset[str]:
        return frozenset(k for k, v in self.prefs.items() if v == "favorite")

    @property
    def hidden(self) -> frozenset[str]:
        return frozenset(k for k, v in self.prefs.items() if v == "hidden")


async def _context(conn: asyncpg.Connection, user: CurrentUser) -> Context:
    equipment = await conn.fetchval(
        "SELECT equipment FROM gyms WHERE user_id = $1 AND is_active", user.id
    )
    injured = await conn.fetchval("SELECT injury_areas FROM profiles WHERE user_id = $1", user.id)
    rows = await conn.fetch(
        "SELECT exercise_id, preference FROM exercise_preferences WHERE user_id = $1", user.id
    )
    return Context(
        frozenset(equipment or []),
        frozenset(injured or []),
        {r["exercise_id"]: r["preference"] for r in rows},
    )


def _summary(e: Exercise, ctx: Context) -> ExerciseSummary:
    return ExerciseSummary(
        id=e.id,
        name=e.name,
        pattern=e.pattern,
        kind=e.kind,
        primary=list(e.primary),
        secondary=list(e.secondary),
        equipment=[list(option) for option in e.equipment],
        difficulty=e.difficulty,
        unilateral=e.unilateral,
        available=is_available(e, ctx.equipment),
        safe=is_safe(e, ctx.injured),
        preference=ctx.prefs.get(e.id, "none"),  # type: ignore[arg-type]
    )


def _get(exercise_id: str) -> Exercise:
    exercise = load_library().get(exercise_id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    return exercise


@router.get("", response_model=list[ExerciseSummary])
async def list_exercises(
    user: CurrentUser = Depends(current_user), conn: asyncpg.Connection = Depends(get_conn)
) -> list[ExerciseSummary]:
    ctx = await _context(conn, user)
    return [_summary(e, ctx) for e in sorted(load_library().values(), key=lambda e: e.name)]


@router.get("/{exercise_id}", response_model=ExerciseDetail)
async def get_exercise(
    exercise_id: str,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> ExerciseDetail:
    exercise = _get(exercise_id)
    ctx = await _context(conn, user)
    alternatives = find_alternatives(
        exercise,
        load_library().values(),
        equipment=ctx.equipment,
        injured=ctx.injured,
        hidden=ctx.hidden,
        favorites=ctx.favorites,
    )
    return ExerciseDetail(
        **_summary(exercise, ctx).model_dump(),
        loads=list(exercise.loads),
        injury_conflicts=sorted(set(exercise.loads) & ctx.injured),
        setup=list(exercise.setup),
        execution=list(exercise.execution),
        breathing=exercise.breathing,
        mistakes=list(exercise.mistakes),
        safety=exercise.safety,
        alternatives=[_summary(a, ctx) for a in alternatives],
    )


class PreferenceIn(BaseModel):
    preference: Preference


@router.put("/{exercise_id}/preference", response_model=PreferenceIn)
async def set_preference(
    exercise_id: str,
    body: PreferenceIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> PreferenceIn:
    _get(exercise_id)  # 404 for unknown exercises
    if body.preference == "none":
        await conn.execute(
            "DELETE FROM exercise_preferences WHERE user_id = $1 AND exercise_id = $2",
            user.id,
            exercise_id,
        )
    else:
        await conn.execute(
            """
            INSERT INTO exercise_preferences (user_id, exercise_id, preference)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, exercise_id)
            DO UPDATE SET preference = EXCLUDED.preference, updated_at = now()
            """,
            user.id,
            exercise_id,
            body.preference,
        )
    return body
