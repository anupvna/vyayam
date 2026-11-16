"""Cardio and floor work: log anything that isn't a lifting set, see this week's
cardio against the goal-based target, and get today's warm-up, finisher, cool-down
and rest-day suggestions. Everything here is optional.
"""

from datetime import date, timedelta
from functools import lru_cache
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.plan import get_today
from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.engine.alternatives import is_available
from app.engine.cardio import (
    ACTIVITY_BY_ID,
    HIIT_MOVES,
    LEVEL_MINUTES,
    Level,
    cardio_level,
    estimate_calories,
    finisher,
    met_for,
    rest_day,
    warmup,
    weekly_target,
)
from app.engine.cooldown import STRETCHES, cooldown, minutes
from app.engine.places import MAT
from app.engine.planner import monday_of
from app.library import load_library

router = APIRouter(prefix="/activities", tags=["activities"])

Part = Literal["warmup", "main", "finisher", "cooldown"]
Intensity = Literal["easy", "moderate", "hard"]

LEGS = {"squat", "hinge", "lunge", "calf_raise"}
NOT_CARDIO = {"stretching", "mat_workout"}  # floor strength and stretching: logged, not cardio


def counts_as_cardio(activity: str, part: str) -> bool:
    return activity not in NOT_CARDIO and part != "cooldown"


@lru_cache
def floor_moves() -> dict[str, tuple[str, str]]:
    """Everything that can be ticked off in a mat workout: id -> (name, group)."""
    moves: dict[str, tuple[str, str]] = {}
    for e in load_library().values():
        if is_available(e, MAT):
            group = "core" if e.pattern == "core" else "legs" if e.pattern in LEGS else "upper"
            moves[e.id] = (e.name, group)
    for mid, name in HIIT_MOVES:
        moves[mid] = (name, "hiit")
    for s in STRETCHES:
        moves[s.id] = (s.name, "stretch")
    return moves


class ActivityIn(BaseModel):
    id: UUID  # made on the phone: a resend is ignored, never duplicated
    day: date
    activity: str
    part: Part = "main"
    minutes: float = Field(gt=0, le=600)
    intensity: Intensity = "moderate"
    speed_kmh: float | None = Field(default=None, gt=0, le=40)
    incline_pct: float | None = Field(default=None, ge=0, le=40)
    level: int | None = Field(default=None, ge=1, le=40)
    distance_km: float | None = Field(default=None, gt=0, le=500)
    calories: int | None = Field(default=None, gt=0, le=5000)
    items: list[str] = Field(default_factory=list, max_length=40)
    note: str = Field(default="", max_length=200)

    @field_validator("activity")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ACTIVITY_BY_ID:
            raise ValueError(f"unknown activity {v!r}")
        return v

    @field_validator("items")
    @classmethod
    def _moves(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(floor_moves())
        if unknown:
            raise ValueError(f"unknown moves {sorted(unknown)}")
        return list(dict.fromkeys(v))  # keep order, drop repeats


class ActivityOut(BaseModel):
    id: UUID
    day: date
    activity: str
    name: str
    part: Part
    minutes: float
    intensity: Intensity
    speed_kmh: float | None
    incline_pct: float | None
    level: int | None
    distance_km: float | None
    calories: int
    calories_estimated: bool  # True: our estimate, not the machine's number
    items: list[str]
    item_names: list[str]
    note: str


async def _weight_kg(conn: asyncpg.Connection, user: CurrentUser, day: date) -> float:
    w = await conn.fetchval(
        """SELECT weight_kg FROM body_weights WHERE user_id = $1 AND day <= $2
           ORDER BY day DESC LIMIT 1""",
        user.id,
        day,
    )
    if w is None:
        w = await conn.fetchval("SELECT weight_kg FROM profiles WHERE user_id = $1", user.id)
    return float(w or 70)


def _out(r: asyncpg.Record, weight_kg: float) -> ActivityOut:
    def num(x):
        return float(x) if x is not None else None

    entered = r["calories"]
    estimate = estimate_calories(
        met_for(r["activity"], intensity=r["intensity"], speed_kmh=num(r["speed_kmh"]),
                incline_pct=num(r["incline_pct"])),
        float(r["minutes"]),
        weight_kg,
    )  # fmt: skip
    moves = floor_moves()
    return ActivityOut(
        id=r["id"],
        day=r["day"],
        activity=r["activity"],
        name=ACTIVITY_BY_ID[r["activity"]].name,
        part=r["part"],
        minutes=float(r["minutes"]),
        intensity=r["intensity"],
        speed_kmh=num(r["speed_kmh"]),
        incline_pct=num(r["incline_pct"]),
        level=r["level"],
        distance_km=num(r["distance_km"]),
        calories=entered or estimate,
        calories_estimated=entered is None,
        items=list(r["items"]),
        item_names=[moves[i][0] for i in r["items"] if i in moves],
        note=r["note"],
    )


async def _between(conn: asyncpg.Connection, user: CurrentUser, start: date, end: date):
    rows = await conn.fetch(
        """SELECT * FROM activity_logs WHERE user_id = $1 AND day BETWEEN $2 AND $3
           ORDER BY day, created_at""",
        user.id,
        start,
        end,
    )
    weight = await _weight_kg(conn, user, end)
    return [_out(r, weight) for r in rows]


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
async def log_activity(
    body: ActivityIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> ActivityOut:
    row = await conn.fetchrow(
        """INSERT INTO activity_logs (id, user_id, day, activity, part, minutes, intensity,
               speed_kmh, incline_pct, level, distance_km, calories, items, note)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
           ON CONFLICT (id) DO NOTHING RETURNING *""",
        body.id, user.id, body.day, body.activity, body.part, body.minutes, body.intensity,
        body.speed_kmh, body.incline_pct, body.level, body.distance_km, body.calories,
        body.items, body.note.strip(),
    )  # fmt: skip
    if row is None:  # already saved (a resend): return it, if it's ours
        row = await conn.fetchrow(
            "SELECT * FROM activity_logs WHERE id = $1 AND user_id = $2", body.id, user.id
        )
        if row is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "That id belongs to another entry")
    return _out(row, await _weight_kg(conn, user, body.day))


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: UUID,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute(
        "DELETE FROM activity_logs WHERE id = $1 AND user_id = $2", activity_id, user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- week and today


class WeekOut(BaseModel):
    level: Level  # what's in effect
    chosen: Level | None  # what the person picked (None: decided by the goal)
    target_minutes: int
    done_minutes: int
    days: list[dict]  # [{date, minutes}] Monday to Sunday
    activities: list[ActivityOut]


class LevelIn(BaseModel):
    level: Level | None  # None: let the goal decide


@router.get("/week", response_model=WeekOut)
async def activity_week(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeekOut:
    profile = await conn.fetchrow(
        "SELECT goal, cardio_level FROM profiles WHERE user_id = $1", user.id
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finish setup first")
    start = monday_of(today)
    items = await _between(conn, user, start, start + timedelta(days=6))
    cardio = [a for a in items if counts_as_cardio(a.activity, a.part)]
    per_day = {start + timedelta(days=i): 0.0 for i in range(7)}
    for a in cardio:
        per_day[a.day] += a.minutes
    return WeekOut(
        level=cardio_level(profile["goal"], profile["cardio_level"]),
        chosen=profile["cardio_level"],
        target_minutes=weekly_target(profile["goal"], profile["cardio_level"]),
        done_minutes=round(sum(per_day.values())),
        days=[{"date": d, "minutes": round(m)} for d, m in per_day.items()],
        activities=items,
    )


@router.put("/level", response_model=WeekOut)
async def set_level(
    body: LevelIn,
    today: date,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeekOut:
    await conn.execute(
        "UPDATE profiles SET cardio_level = $2 WHERE user_id = $1", user.id, body.level
    )
    return await activity_week(today=today, user=user, conn=conn)


class SuggestionOut(BaseModel):
    activity: str
    minutes: int
    text: str
    done: bool


class StretchOut(BaseModel):
    id: str
    name: str
    seconds: int
    each_side: bool
    how: str


class TodayOut(BaseModel):
    warmup: SuggestionOut | None
    finisher: SuggestionOut | None
    cooldown: list[StretchOut]
    cooldown_minutes: int
    rest_day: str | None
    activities: list[ActivityOut]
    week_target: int
    week_done: int


async def _equipment_today(conn: asyncpg.Connection, user: CurrentUser, day: date) -> frozenset:
    place = await conn.fetchrow(
        """SELECT p.mat_only, g.equipment FROM day_places p LEFT JOIN gyms g ON g.id = p.gym_id
           WHERE p.user_id = $1 AND p.day = $2""",
        user.id,
        day,
    )
    if place is not None:
        return MAT if place["mat_only"] else frozenset(place["equipment"])
    eq = await conn.fetchval("SELECT equipment FROM gyms WHERE user_id = $1 AND is_active", user.id)
    return frozenset(eq or [])


@router.get("/today", response_model=TodayOut)
async def activity_today(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> TodayOut:
    week = await activity_week(today=today, user=user, conn=conn)
    day = await get_today(today=today, minutes=None, user=user, conn=conn)
    equipment = await _equipment_today(conn, user, today)
    goal = await conn.fetchval("SELECT goal FROM profiles WHERE user_id = $1", user.id)
    mine = [a for a in week.activities if a.day == today]
    parts = {a.part for a in mine}

    def suggestion(s, part: str) -> SuggestionOut | None:
        if s is None:
            return None
        return SuggestionOut(
            activity=s.activity, minutes=s.minutes, text=s.text, done=part in parts
        )

    training = day.status == "planned" and bool(day.exercises)
    stretches = []
    if training:
        muscles = list(dict.fromkeys(m for e in day.exercises for m in e.primary))
        stretches = cooldown(muscles)
    return TodayOut(
        warmup=suggestion(warmup(equipment), "warmup") if training else None,
        finisher=suggestion(finisher(goal, week.level, equipment), "finisher")
        if training
        else None,
        cooldown=[StretchOut(**vars(s)) for s in stretches],
        cooldown_minutes=minutes(stretches) if stretches else 0,
        rest_day=None if training else rest_day(week.level, week.done_minutes, week.target_minutes),
        activities=mine,
        week_target=week.target_minutes,
        week_done=week.done_minutes,
    )


LEVEL_NAMES = {"none": "None", "light": "Light", "regular": "Regular", "lots": "Lots"}


def catalog() -> dict:
    """For /catalog: what can be logged, and the cardio levels."""
    return {
        "activities": [
            {"id": a.id, "name": a.name, "group": a.group, "fields": list(a.fields),
             "equipment": a.equipment}
            for a in ACTIVITY_BY_ID.values()
        ],
        "floor_moves": [
            {"id": i, "name": name, "group": group} for i, (name, group) in floor_moves().items()
        ],
        "cardio_levels": [
            {"id": k, "name": LEVEL_NAMES[k], "minutes": v} for k, v in LEVEL_MINUTES.items()
        ],
    }  # fmt: skip
