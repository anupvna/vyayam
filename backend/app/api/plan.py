"""Plan endpoints: choose a split, see the week, see today, skip or swap a day.

The plan is never stored. It's recomputed on every request from the profile, active
gym, preferences, split and day overrides, by the pure planner engine. That keeps
it consistent (change your gym, and the plan follows) and makes it cheap to test.

Dates come from the client (`?today=YYYY-MM-DD`) because "today" depends on the
user's time zone, not the server's.
"""

import json
from dataclasses import replace
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.catalog import MUSCLE_IDS
from app.engine.places import MAT, substitute_day
from app.engine.planner import (
    DayPlan,
    Override,
    PlanContext,
    WeekPlan,
    hard_muscles,
    monday_of,
    plan_week,
    trim_to_minutes,
)
from app.engine.splits import (
    SPLITS,
    TEMPLATES,
    SessionTemplate,
    recommend_split,
    template_from_muscles,
)
from app.library import load_library

router = APIRouter(prefix="/plan", tags=["plan"])


# ---------------------------------------------------------------- models


class CustomSession(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    muscles: list[str] = Field(min_length=1, max_length=6)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("muscles")
    @classmethod
    def _muscles(cls, v: list[str]) -> list[str]:
        unknown = set(v) - MUSCLE_IDS
        if unknown:
            raise ValueError(f"unknown muscles: {sorted(unknown)}")
        return list(dict.fromkeys(v))


class SplitIn(BaseModel):
    split_id: str
    custom_sessions: list[CustomSession] | None = Field(default=None, max_length=7)
    today: date

    @field_validator("split_id")
    @classmethod
    def _known(cls, v: str) -> str:
        if v != "custom" and v not in SPLITS:
            raise ValueError("unknown split")
        return v


class SessionOut(BaseModel):
    key: str
    name: str
    focus: list[str]


class SplitOut(BaseModel):
    id: str
    name: str
    blurb: str
    designed_for: list[int]
    sessions: list[SessionOut]
    fit_note: str | None = None


class SplitsOut(BaseModel):
    recommended: str
    reason: str
    current: str | None
    splits: list[SplitOut]


class PlannedExerciseOut(BaseModel):
    exercise_id: str
    name: str
    kind: str
    primary: list[str]
    sets: int
    reps: tuple[int, int]
    rir: int
    rest_seconds: int
    light: bool


class DayOut(BaseModel):
    date: date
    status: Literal["rest", "planned", "skipped"]
    session_key: str | None
    session_name: str | None
    focus: list[str]
    minutes: int
    exercises: list[PlannedExerciseOut]
    notes: list[str]
    swapped: bool
    moved: bool
    logged_sets: int = 0
    place: str | None = None  # e.g. "home (mat only)" when not at the active gym


class WeekOut(BaseModel):
    start: date
    week_index: int
    deload: bool
    notes: list[str]
    split: SplitOut
    days: list[DayOut]


class SwapIn(BaseModel):
    session_key: str | None = None
    muscles: list[str] = Field(default_factory=list, max_length=6)
    today: date

    @field_validator("muscles")
    @classmethod
    def _muscles(cls, v: list[str]) -> list[str]:
        unknown = set(v) - MUSCLE_IDS
        if unknown:
            raise ValueError(f"unknown muscles: {sorted(unknown)}")
        return list(dict.fromkeys(v))


class TodayIn(BaseModel):
    today: date


# ---------------------------------------------------------------- loading state


async def _context(conn: asyncpg.Connection, user: CurrentUser) -> PlanContext:
    profile = await conn.fetchrow(
        """SELECT experience, goal, training_days, session_minutes, injury_areas
           FROM profiles WHERE user_id = $1""",
        user.id,
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finish setup first")
    equipment = await conn.fetchval(
        "SELECT equipment FROM gyms WHERE user_id = $1 AND is_active", user.id
    )
    prefs = await conn.fetch(
        "SELECT exercise_id, preference FROM exercise_preferences WHERE user_id = $1", user.id
    )
    return PlanContext(
        experience=profile["experience"],
        goal=profile["goal"],
        training_days=tuple(profile["training_days"]),
        session_minutes=profile["session_minutes"],
        equipment=frozenset(equipment or []),
        injured=frozenset(profile["injury_areas"]),
        favorites=frozenset(r["exercise_id"] for r in prefs if r["preference"] == "favorite"),
        hidden=frozenset(r["exercise_id"] for r in prefs if r["preference"] == "hidden"),
    )


def _cycle(split_id: str, custom: list[dict] | None) -> list[SessionTemplate]:
    if split_id == "custom":
        return [
            template_from_muscles(f"custom_{i}", s["name"], s["muscles"])
            for i, s in enumerate(custom or [])
        ]
    return [TEMPLATES[k] for k in SPLITS[split_id].cycle]


async def _split(conn: asyncpg.Connection, user: CurrentUser):
    row = await conn.fetchrow(
        "SELECT split_id, custom_sessions, started_on FROM user_splits WHERE user_id = $1",
        user.id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Choose a split first")
    custom = json.loads(row["custom_sessions"]) if row["custom_sessions"] else None
    return row["split_id"], custom, row["started_on"]


async def _overrides(conn: asyncpg.Connection, user: CurrentUser, start: date) -> dict:
    rows = await conn.fetch(
        """SELECT day, action, session_key, muscles FROM day_overrides
           WHERE user_id = $1 AND day BETWEEN $2 AND $3""",
        user.id,
        start,
        start + timedelta(days=6),
    )
    return {r["day"]: Override(r["action"], r["session_key"], tuple(r["muscles"])) for r in rows}


def _num(x: float) -> str:
    """2.0 -> "2", 1.33 -> "1.3"."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _split_out(split_id: str, custom: list[dict] | None, days: tuple[int, ...]) -> SplitOut:
    cyc = _cycle(split_id, custom)
    sessions = [SessionOut(key=t.key, name=t.name, focus=list(t.focus)) for t in cyc]
    if split_id == "custom":
        return SplitOut(
            id="custom",
            name="Your custom split",
            blurb="Sessions you designed.",
            designed_for=[len(cyc)],
            sessions=sessions,
        )
    s = SPLITS[split_id]
    fit = None
    if len(days) not in s.designed_for:
        per_week = len(days) / len(cyc)
        fit = (
            f"Built for {' or '.join(map(str, s.designed_for))} days a week. On your "
            f"{len(days)} days each session comes around about "
            + (
                f"{_num(per_week)} times a week."
                if per_week >= 1
                else f"every {_num(len(cyc) / len(days))} weeks."
            )
        )
    return SplitOut(
        id=s.id,
        name=s.name,
        blurb=s.blurb,
        designed_for=list(s.designed_for),
        sessions=sessions,
        fit_note=fit,
    )


FATIGUE_MIN_CHECKINS = 3
FATIGUE_SCORE = 45  # average readiness below this over recent days -> deload


async def _run_down(conn: asyncpg.Connection, user: CurrentUser, today: date) -> bool:
    """Fatigue signal: at least 3 check-ins in the last 10 days averaging below 45."""
    row = await conn.fetchrow(
        """SELECT count(*) AS n, avg(score) AS avg FROM readiness_checkins
           WHERE user_id = $1 AND day BETWEEN $2 AND $3""",
        user.id,
        today - timedelta(days=9),
        today,
    )
    return row["n"] >= FATIGUE_MIN_CHECKINS and float(row["avg"]) < FATIGUE_SCORE


async def _week(
    conn: asyncpg.Connection,
    user: CurrentUser,
    any_day: date,
    today: date,
    *,
    extra_injured: frozenset[str] = frozenset(),
) -> tuple[WeekPlan, SplitOut]:
    ctx = await _context(conn, user)
    if extra_injured:  # areas that hurt today (from the readiness check-in)
        ctx = replace(ctx, injured=ctx.injured | extra_injured)
    split_id, custom, started_on = await _split(conn, user)
    cyc = _cycle(split_id, custom)
    library = list(load_library().values())
    start = monday_of(any_day)
    index = max(0, (start - monday_of(started_on)).days // 7)

    previous_hard: frozenset[str] = frozenset()
    if index > 0:  # last week's Sunday affects this Monday's recovery
        prev_start = start - timedelta(days=7)
        prev = plan_week(
            ctx,
            cyc,
            library,
            week_start=prev_start,
            week_index=index - 1,
            overrides=await _overrides(conn, user, prev_start),
            today=today,
        )
        previous_hard = hard_muscles(prev.days[-1])

    tired = start <= today < start + timedelta(days=7) and await _run_down(conn, user, today)
    week = plan_week(
        ctx,
        cyc,
        library,
        week_start=start,
        week_index=index,
        overrides=await _overrides(conn, user, start),
        today=today,
        previous_hard=previous_hard,
        force_deload=tired,
    )
    if tired:
        week.notes.insert(
            0, "Your recent check-ins show you're run down, so this week is a deload."
        )
    places = await _places(conn, user, start)
    if places:
        lib = load_library()
        week.days = [
            substitute_day(
                d,
                lib,
                equipment=places[d.date][1],
                place_name=places[d.date][0],
                injured=ctx.injured,
                hidden=ctx.hidden,
                favorites=ctx.favorites,
            )
            if d.date in places
            else d
            for d in week.days
        ]
        for d in week.days:
            if d.date in places and d.status == "planned":
                d.place = places[d.date][0]
    return week, _split_out(split_id, custom, ctx.training_days)


MAT_PLACE = "home (mat only)"


async def _places(
    conn: asyncpg.Connection, user: CurrentUser, start: date
) -> dict[date, tuple[str, frozenset[str]]]:
    """Days this week trained somewhere other than the active gym: name and equipment."""
    rows = await conn.fetch(
        """SELECT p.day, p.mat_only, g.name, g.equipment FROM day_places p
           LEFT JOIN gyms g ON g.id = p.gym_id
           WHERE p.user_id = $1 AND p.day BETWEEN $2 AND $3""",
        user.id,
        start,
        start + timedelta(days=6),
    )
    return {
        r["day"]: (MAT_PLACE, MAT) if r["mat_only"] else (r["name"], frozenset(r["equipment"]))
        for r in rows
    }


def _day_out(d: DayPlan) -> DayOut:
    return DayOut(
        date=d.date,
        status=d.status,
        session_key=d.session_key,
        session_name=d.session_name,
        focus=list(d.focus),
        minutes=d.minutes,
        exercises=[
            PlannedExerciseOut(
                exercise_id=e.exercise_id,
                name=e.name,
                kind=e.kind,
                primary=list(e.primary),
                sets=e.sets,
                reps=e.reps,
                rir=e.rir,
                rest_seconds=e.rest_seconds,
                light=e.light,
            )
            for e in d.exercises
        ],
        notes=d.notes,
        swapped=d.swapped,
        moved=d.moved,
        place=d.place,
    )


# ---------------------------------------------------------------- splits


@router.get("/splits", response_model=SplitsOut)
async def list_splits(
    user: CurrentUser = Depends(current_user), conn: asyncpg.Connection = Depends(get_conn)
) -> SplitsOut:
    ctx = await _context(conn, user)
    rec, reason = recommend_split(list(ctx.training_days), ctx.experience, ctx.goal)
    current = await conn.fetchval("SELECT split_id FROM user_splits WHERE user_id = $1", user.id)
    return SplitsOut(
        recommended=rec,
        reason=reason,
        current=current,
        splits=[_split_out(s, None, ctx.training_days) for s in SPLITS],
    )


@router.put("/split", response_model=SplitOut)
async def choose_split(
    body: SplitIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> SplitOut:
    ctx = await _context(conn, user)
    if body.split_id == "custom" and not body.custom_sessions:
        raise HTTPException(422, "Add at least one session")
    custom = (
        [s.model_dump() for s in body.custom_sessions]
        if body.split_id == "custom" and body.custom_sessions
        else None
    )
    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO user_splits (user_id, split_id, custom_sessions, started_on)
            VALUES ($1, $2, $3::jsonb, $4)
            ON CONFLICT (user_id) DO UPDATE SET split_id = EXCLUDED.split_id,
                custom_sessions = EXCLUDED.custom_sessions, started_on = EXCLUDED.started_on,
                updated_at = now()
            """,
            user.id,
            body.split_id,
            json.dumps(custom) if custom else None,
            monday_of(body.today),
        )
        # Swaps and skips from today on referred to the old split's sessions.
        await conn.execute(
            "DELETE FROM day_overrides WHERE user_id = $1 AND day >= $2", user.id, body.today
        )
    return _split_out(body.split_id, custom, ctx.training_days)


# ---------------------------------------------------------------- week and today


@router.get("/week", response_model=WeekOut)
async def get_week(
    today: date,
    day: date | None = None,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeekOut:
    week, split = await _week(conn, user, day or today, today)
    counts = dict(
        await conn.fetch(
            """SELECT day, count(*) FROM set_logs WHERE user_id = $1 AND day BETWEEN $2 AND $3
               GROUP BY day""",
            user.id,
            week.start,
            week.start + timedelta(days=6),
        )
    )
    days = [_day_out(d) for d in week.days]
    for d in days:
        d.logged_sets = counts.get(d.date, 0)
    return WeekOut(
        start=week.start,
        week_index=week.week_index,
        deload=week.deload,
        notes=week.notes,
        split=split,
        days=days,
    )


@router.get("/today", response_model=DayOut)
async def get_today(
    today: date,
    minutes: int | None = Query(default=None, ge=20, le=180),
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> DayOut:
    week, _ = await _week(conn, user, today, today)
    day = next(d for d in week.days if d.date == today)
    if minutes is not None and day.status == "planned" and day.minutes > minutes:
        day.exercises = trim_to_minutes(day.exercises, minutes)
        day.notes.append(
            f"Shortened to fit {minutes} minutes: main lifts kept, accessories trimmed."
        )
    return _day_out(day)


# ---------------------------------------------------------------- skip and swap


async def _check_training_day(conn: asyncpg.Connection, user: CurrentUser, day: date, today: date):
    ctx = await _context(conn, user)
    if day.weekday() not in ctx.training_days:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That's a rest day. Rest days stay rest days."
        )
    if day < monday_of(today):
        raise HTTPException(status.HTTP_409_CONFLICT, "Past weeks can't be changed.")


@router.post("/days/{day}/skip", response_model=WeekOut)
async def skip_day(
    day: date,
    body: TodayIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeekOut:
    await _check_training_day(conn, user, day, body.today)
    await conn.execute(
        """INSERT INTO day_overrides (user_id, day, action) VALUES ($1, $2, 'skip')
           ON CONFLICT (user_id, day) DO UPDATE SET action = 'skip', session_key = NULL,
           muscles = '{}', created_at = now()""",
        user.id,
        day,
    )
    return await get_week(today=body.today, day=day, user=user, conn=conn)


@router.post("/days/{day}/swap", response_model=WeekOut)
async def swap_day(
    day: date,
    body: SwapIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeekOut:
    await _check_training_day(conn, user, day, body.today)
    split_id, custom, _ = await _split(conn, user)
    keys = {t.key for t in _cycle(split_id, custom)}
    if body.session_key is None and not body.muscles:
        raise HTTPException(422, "Pick a session or some muscles")
    if body.session_key is not None and body.session_key not in keys:
        raise HTTPException(422, "That session isn't in your split")
    await conn.execute(
        """INSERT INTO day_overrides (user_id, day, action, session_key, muscles)
           VALUES ($1, $2, 'swap', $3, $4)
           ON CONFLICT (user_id, day) DO UPDATE SET action = 'swap',
           session_key = EXCLUDED.session_key, muscles = EXCLUDED.muscles, created_at = now()""",
        user.id,
        day,
        body.session_key,
        [] if body.session_key else body.muscles,
    )
    return await get_week(today=body.today, day=day, user=user, conn=conn)


class PlaceIn(BaseModel):
    today: date
    gym_id: UUID | None = None  # one of your gyms...
    mat: bool = False  # ...or at home with just a mat

    @model_validator(mode="after")
    def _one(self) -> "PlaceIn":
        if self.mat == (self.gym_id is not None):
            raise ValueError("Choose either a gym or the mat")
        return self


@router.put("/days/{day}/place", response_model=DayOut)
async def set_place(
    day: date,
    body: PlaceIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> DayOut:
    """Train somewhere else for one day; the active gym stays the default."""
    if day < body.today or day > body.today + timedelta(days=13):
        raise HTTPException(status.HTTP_409_CONFLICT, "Pick today or a day in the next two weeks.")
    if body.gym_id is not None:
        gym = await conn.fetchrow(
            "SELECT is_active FROM gyms WHERE id = $1 AND user_id = $2", body.gym_id, user.id
        )
        if gym is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")
        if gym["is_active"]:  # back to the usual gym: nothing to override
            await conn.execute(
                "DELETE FROM day_places WHERE user_id = $1 AND day = $2", user.id, day
            )
            return await get_today(today=day, minutes=None, user=user, conn=conn)
    await conn.execute(
        """INSERT INTO day_places (user_id, day, gym_id, mat_only) VALUES ($1, $2, $3, $4)
           ON CONFLICT (user_id, day) DO UPDATE SET gym_id = EXCLUDED.gym_id,
           mat_only = EXCLUDED.mat_only""",
        user.id,
        day,
        body.gym_id,
        body.mat,
    )
    return await get_today(today=day, minutes=None, user=user, conn=conn)


@router.delete("/days/{day}/place", status_code=status.HTTP_204_NO_CONTENT)
async def reset_place(
    day: date,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute("DELETE FROM day_places WHERE user_id = $1 AND day = $2", user.id, day)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/days/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def restore_day(
    day: date,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute("DELETE FROM day_overrides WHERE user_id = $1 AND day = $2", user.id, day)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
