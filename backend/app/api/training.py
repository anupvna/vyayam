"""Training endpoints: readiness check-in, logging sets, and today's workout with
targets.

Order of decisions for today's workout:
  1. Safety layer: a red flag stops training. Nothing else runs.
  2. Pain: areas that hurt today are excluded, like injuries.
  3. Readiness: "lighter" removes a set per exercise and eases effort; "rest"
     suggests resting and offers an easy version; sore muscles are kept light.
  4. Time: shorten to the minutes available, if asked.
  5. Targets: double progression from your history, per exercise.
"""

from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from app.api.plan import DayOut, _day_out, _week
from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.catalog import BODY_PART_IDS
from app.engine.planner import LIGHT_MAX_SETS, LIGHT_RIR, trim_to_minutes
from app.engine.progression import (
    LoggedSet,
    Session,
    e1rm,
    is_pr,
    load_type,
    next_target,
)
from app.engine.readiness import RED_FLAGS, SORE_AREAS, Assessment, CheckIn, assess
from app.library import load_library

router = APIRouter(tags=["training"])


# ---------------------------------------------------------------- readiness


class CheckInIn(BaseModel):
    today: date
    sleep: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    sore_areas: list[str] = Field(default_factory=list)
    pain_areas: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    @field_validator("sore_areas")
    @classmethod
    def _sore(cls, v: list[str]) -> list[str]:
        if set(v) - set(SORE_AREAS):
            raise ValueError("unknown sore area")
        return sorted(set(v))

    @field_validator("pain_areas")
    @classmethod
    def _pain(cls, v: list[str]) -> list[str]:
        if set(v) - BODY_PART_IDS:
            raise ValueError("unknown body part")
        return sorted(set(v))

    @field_validator("red_flags")
    @classmethod
    def _flags(cls, v: list[str]) -> list[str]:
        if set(v) - set(RED_FLAGS):
            raise ValueError("unknown symptom")
        return sorted(set(v))


class AssessmentOut(BaseModel):
    verdict: str
    score: int
    messages: list[str]
    avoid_areas: list[str]
    sore_areas: list[str]


async def _assessment(
    conn: asyncpg.Connection, user: CurrentUser, today: date
) -> tuple[Assessment, list[str]] | None:
    row = await conn.fetchrow(
        "SELECT * FROM readiness_checkins WHERE user_id = $1 AND day = $2", user.id, today
    )
    if row is None:
        return None
    history = await conn.fetch(
        """SELECT unnest(pain_areas) AS area, count(*) AS n FROM readiness_checkins
           WHERE user_id = $1 AND day BETWEEN $2 AND $3 GROUP BY area""",
        user.id,
        today - timedelta(days=13),
        today,
    )
    c = CheckIn(
        row["sleep"],
        row["energy"],
        row["stress"],
        frozenset(row["sore_areas"]),
        frozenset(row["pain_areas"]),
        frozenset(row["red_flags"]),
    )
    return assess(c, {r["area"]: r["n"] for r in history}), list(row["sore_areas"])


def _assessment_out(a: Assessment, sore: list[str]) -> AssessmentOut:
    return AssessmentOut(
        verdict=a.verdict,
        score=a.score,
        messages=list(a.messages),
        avoid_areas=sorted(a.avoid_areas),
        sore_areas=sore,
    )


@router.post("/readiness", response_model=AssessmentOut)
async def check_in(
    body: CheckInIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> AssessmentOut:
    c = CheckIn(
        body.sleep,
        body.energy,
        body.stress,
        frozenset(body.sore_areas),
        frozenset(body.pain_areas),
        frozenset(body.red_flags),
    )
    first = assess(c)
    await conn.execute(
        """
        INSERT INTO readiness_checkins
            (user_id, day, sleep, energy, stress, sore_areas, pain_areas, red_flags, score, verdict)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (user_id, day) DO UPDATE SET sleep = EXCLUDED.sleep, energy = EXCLUDED.energy,
            stress = EXCLUDED.stress, sore_areas = EXCLUDED.sore_areas,
            pain_areas = EXCLUDED.pain_areas, red_flags = EXCLUDED.red_flags,
            score = EXCLUDED.score, verdict = EXCLUDED.verdict, created_at = now()
        """,
        user.id,
        body.today,
        body.sleep,
        body.energy,
        body.stress,
        body.sore_areas,
        body.pain_areas,
        body.red_flags,
        first.score,
        first.verdict,
    )
    a, sore = await _assessment(conn, user, body.today)  # type: ignore[misc]
    return _assessment_out(a, sore)


@router.get("/readiness", response_model=AssessmentOut)
async def get_check_in(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> AssessmentOut:
    found = await _assessment(conn, user, today)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No check-in today")
    return _assessment_out(*found)


# ---------------------------------------------------------------- logging sets


class SetIn(BaseModel):
    id: UUID  # generated by the app, so retries can't create duplicates
    day: date
    exercise_id: str
    set_index: int = Field(ge=1, le=20)
    weight_kg: float = Field(ge=0, le=1000)
    reps: int = Field(ge=0, le=100)
    rir: int | None = Field(default=None, ge=0, le=10)
    note: str = Field(default="", max_length=200)

    @field_validator("exercise_id")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in load_library():
            raise ValueError("unknown exercise")
        return v


class SetOut(BaseModel):
    id: UUID
    day: date
    exercise_id: str
    set_index: int
    weight_kg: float
    reps: int
    rir: int | None
    note: str
    e1rm: float | None
    pr: bool


async def _set_out(conn: asyncpg.Connection, user: CurrentUser, row: asyncpg.Record) -> SetOut:
    earlier = await conn.fetch(
        """SELECT weight_kg, reps FROM set_logs
           WHERE user_id = $1 AND exercise_id = $2 AND id <> $3
             AND (logged_at, id) < ($4, $3)""",
        user.id,
        row["exercise_id"],
        row["id"],
        row["logged_at"],
    )
    this = LoggedSet(row["weight_kg"], row["reps"])
    value = e1rm(this.weight_kg, this.reps)
    return SetOut(
        id=row["id"],
        day=row["day"],
        exercise_id=row["exercise_id"],
        set_index=row["set_index"],
        weight_kg=row["weight_kg"],
        reps=row["reps"],
        rir=row["rir"],
        note=row["note"],
        e1rm=round(value, 1) if value else None,
        pr=is_pr(this, [LoggedSet(r["weight_kg"], r["reps"]) for r in earlier]),
    )


@router.post("/logs", response_model=SetOut)
async def log_set(
    body: SetIn,
    response: Response,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> SetOut:
    inserted = await conn.fetchrow(
        """
        INSERT INTO set_logs (id, user_id, day, exercise_id, set_index, weight_kg, reps, rir, note)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO NOTHING
        RETURNING *
        """,
        body.id,
        user.id,
        body.day,
        body.exercise_id,
        body.set_index,
        body.weight_kg,
        body.reps,
        body.rir,
        body.note,
    )
    if inserted is None:  # a replay of a set we already have
        existing = await conn.fetchrow(
            "SELECT * FROM set_logs WHERE id = $1 AND user_id = $2", body.id, user.id
        )
        if existing is None:  # that id belongs to someone else: refuse, reveal nothing
            raise HTTPException(status.HTTP_409_CONFLICT, "Conflicting set id")
        response.status_code = status.HTTP_200_OK
        return await _set_out(conn, user, existing)
    response.status_code = status.HTTP_201_CREATED
    return await _set_out(conn, user, inserted)


@router.delete("/logs/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(
    set_id: UUID,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute("DELETE FROM set_logs WHERE id = $1 AND user_id = $2", set_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/logs", response_model=list[SetOut])
async def list_sets(
    day: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[SetOut]:
    rows = await conn.fetch(
        "SELECT * FROM set_logs WHERE user_id = $1 AND day = $2 ORDER BY logged_at, id",
        user.id,
        day,
    )
    return [await _set_out(conn, user, r) for r in rows]


# ---------------------------------------------------------------- today's workout


class TargetOut(BaseModel):
    weight_kg: float | None
    reps: int
    reason: str
    change: str


class LastSet(BaseModel):
    weight_kg: float
    reps: int


class LastSession(BaseModel):
    day: date
    sets: list[LastSet]


class TodayExercise(BaseModel):
    exercise_id: str
    target: TargetOut
    logged: list[SetOut]
    # How it's loaded with today's gear: barbell_*, dumbbell (weights are per dumbbell),
    # machine_*, or None for bodyweight and bands. Lets the screen label the weight.
    load: str | None
    last: LastSession | None  # the previous session of this exercise, set by set


class TodayOut(BaseModel):
    day: DayOut
    stop: bool
    suggest_rest: bool
    deload: bool
    readiness: AssessmentOut | None
    exercises: list[TodayExercise]


async def _history(
    conn: asyncpg.Connection, user: CurrentUser, exercise_id: str, before: date
) -> list[Session]:
    rows = await conn.fetch(
        """SELECT day, weight_kg, reps, rir FROM set_logs
           WHERE user_id = $1 AND exercise_id = $2 AND day < $3
             AND day >= (SELECT coalesce(min(d), $3) FROM (
                 SELECT DISTINCT day AS d FROM set_logs
                 WHERE user_id = $1 AND exercise_id = $2 AND day < $3
                 ORDER BY d DESC LIMIT 6) recent)
           ORDER BY day DESC, logged_at""",
        user.id,
        exercise_id,
        before,
    )
    by_day: dict[date, list[LoggedSet]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(LoggedSet(r["weight_kg"], r["reps"], r["rir"]))
    return [Session(d, tuple(s)) for d, s in sorted(by_day.items(), reverse=True)]


@router.get("/training/today", response_model=TodayOut)
async def training_today(
    today: date,
    minutes: int | None = Query(default=None, ge=20, le=180),
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> TodayOut:
    found = await _assessment(conn, user, today)
    a, sore = found if found else (None, [])

    week, _ = await _week(
        conn, user, today, today, extra_injured=a.avoid_areas if a else frozenset()
    )
    day = next(d for d in week.days if d.date == today)
    stop = a is not None and a.verdict == "stop"
    suggest_rest = a is not None and a.verdict == "rest"

    if stop:  # safety layer: no workout at all
        day.exercises = []
    elif a is not None and day.status == "planned":
        for e in day.exercises:
            if suggest_rest or set(e.primary) & a.sore_muscles:
                e.light, e.sets, e.rir = True, min(e.sets, LIGHT_MAX_SETS), LIGHT_RIR
            elif a.verdict == "lighter":
                e.sets, e.rir = max(1, e.sets - 1), min(e.rir + 1, LIGHT_RIR)
        day.notes = list(a.messages) + day.notes
    if minutes is not None and day.status == "planned" and day.minutes > minutes:
        day.exercises = trim_to_minutes(day.exercises, minutes)
        day.notes.append(
            f"Shortened to fit {minutes} minutes: main lifts kept, accessories trimmed."
        )

    profile = await conn.fetchrow("SELECT unit_system FROM profiles WHERE user_id = $1", user.id)
    equipment = frozenset(
        await conn.fetchval("SELECT equipment FROM gyms WHERE user_id = $1 AND is_active", user.id)
        or []
    )
    library = load_library()
    logged_rows = await conn.fetch(
        "SELECT * FROM set_logs WHERE user_id = $1 AND day = $2 ORDER BY logged_at, id",
        user.id,
        today,
    )
    logged: dict[str, list[SetOut]] = defaultdict(list)
    for r in logged_rows:
        logged[r["exercise_id"]].append(await _set_out(conn, user, r))

    exercises = []
    for e in day.exercises:
        history = await _history(conn, user, e.exercise_id, today)
        load = load_type(library[e.exercise_id], equipment)
        t = next_target(
            history,
            e.reps,
            load,
            profile["unit_system"],
            rir=e.rir,
            light=e.light,
            deload=week.deload,
        )
        exercises.append(
            TodayExercise(
                exercise_id=e.exercise_id,
                target=TargetOut(
                    weight_kg=t.weight_kg, reps=t.reps, reason=t.reason, change=t.change
                ),
                logged=logged.get(e.exercise_id, []),
                load=load,
                last=LastSession(
                    day=history[0].day,
                    sets=[LastSet(weight_kg=x.weight_kg, reps=x.reps) for x in history[0].sets],
                )
                if history
                else None,
            )
        )

    out = _day_out(day)
    out.logged_sets = len(logged_rows)
    return TodayOut(
        day=out,
        stop=stop,
        suggest_rest=suggest_rest,
        deload=week.deload,
        readiness=_assessment_out(a, sore) if a else None,
        exercises=exercises,
    )


# ---------------------------------------------------------------- history (for charts)


class HistoryPoint(BaseModel):
    day: date
    best_e1rm: float | None
    top_weight_kg: float
    total_reps: int
    pr: bool


@router.get("/exercises/{exercise_id}/history", response_model=list[HistoryPoint])
async def exercise_history(
    exercise_id: str,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[HistoryPoint]:
    if exercise_id not in load_library():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    rows = await conn.fetch(
        """SELECT day, weight_kg, reps FROM set_logs WHERE user_id = $1 AND exercise_id = $2
           ORDER BY day, logged_at""",
        user.id,
        exercise_id,
    )
    by_day: dict[date, list[LoggedSet]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(LoggedSet(r["weight_kg"], r["reps"]))
    points, best = [], None
    for d, sets in sorted(by_day.items()):
        values = [v for s in sets if (v := e1rm(s.weight_kg, s.reps)) is not None]
        top = max(values) if values else None
        pr = top is not None and best is not None and top > best
        if top is not None:
            best = top if best is None else max(best, top)
        points.append(
            HistoryPoint(
                day=d,
                best_e1rm=round(top, 1) if top else None,
                top_weight_kg=max(s.weight_kg for s in sets),
                total_reps=sum(s.reps for s in sets),
                pr=pr,
            )
        )
    return points
