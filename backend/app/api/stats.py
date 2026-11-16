"""Progress stats, computed from logged sets, the plan, and check-ins.

- volume: hard sets per muscle per week vs. the planner's targets, plus push/pull
  balance for the current week.
- calendar: each day marked done / missed / skipped / rest / upcoming.
- recovery: each muscle fresh / recovering / fatigued, from the last 3 days of
  training and today's soreness.
- summary: this week vs last week in plain words.
- exercises: what you've logged, for the strength chart.

A set counts 1 for its exercise's primary muscles and 0.5 for secondary muscles,
the same rule the planner uses, so charts and plans agree.
"""

from collections import defaultdict
from datetime import date, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.deps import CurrentUser, current_user, get_conn
from app.catalog import MUSCLES
from app.engine.planner import ALL_MUSCLES, monday_of, target_range
from app.engine.progression import e1rm
from app.engine.readiness import SORE_AREAS
from app.library import load_library

_MUSCLE_NAMES = {m.id: m.name for m in MUSCLES}

router = APIRouter(prefix="/stats", tags=["stats"])

PUSH_PATTERNS = {
    "horizontal_push",
    "vertical_push",
    "chest_fly",
    "lateral_raise",
    "elbow_extension",
}
PULL_PATTERNS = {"horizontal_pull", "vertical_pull", "rear_delt_fly", "elbow_flexion", "shrug"}
HARD_SETS_FOR_FATIGUE = 3


async def _profile(conn: asyncpg.Connection, user: CurrentUser) -> asyncpg.Record:
    row = await conn.fetchrow(
        "SELECT experience, training_days FROM profiles WHERE user_id = $1", user.id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finish setup first")
    return row


async def _sets(conn: asyncpg.Connection, user: CurrentUser, start: date, end: date):
    return await conn.fetch(
        """SELECT day, exercise_id, weight_kg, reps FROM set_logs
           WHERE user_id = $1 AND day BETWEEN $2 AND $3 ORDER BY day""",
        user.id,
        start,
        end,
    )


def _muscle_sets(rows) -> dict[date, dict[str, float]]:
    lib = load_library()
    out: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        ex = lib.get(r["exercise_id"])
        if ex is None:
            continue
        for m in ex.primary:
            out[r["day"]][m] += 1
        for m in ex.secondary:
            out[r["day"]][m] += 0.5
    return out


# ---------------------------------------------------------------- volume


class MuscleVolume(BaseModel):
    muscle: str
    weekly: list[float]  # oldest first, aligned with `weeks`
    target_low: int
    target_high: int


class VolumeOut(BaseModel):
    weeks: list[date]
    muscles: list[MuscleVolume]
    push_sets: int
    pull_sets: int


@router.get("/volume", response_model=VolumeOut)
async def volume(
    today: date,
    weeks: int = Query(default=8, ge=1, le=26),
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> VolumeOut:
    profile = await _profile(conn, user)
    this_monday = monday_of(today)
    starts = [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    rows = await _sets(conn, user, starts[0], this_monday + timedelta(days=6))
    by_day = _muscle_sets(rows)
    weekly = {m: [0.0] * weeks for m in ALL_MUSCLES}
    for day, muscles in by_day.items():
        i = (monday_of(day) - starts[0]).days // 7
        for m, v in muscles.items():
            weekly[m][i] += v
    lib = load_library()
    push = pull = 0
    for r in rows:
        if monday_of(r["day"]) == this_monday and (ex := lib.get(r["exercise_id"])):
            push += ex.pattern in PUSH_PATTERNS
            pull += ex.pattern in PULL_PATTERNS
    return VolumeOut(
        weeks=starts,
        muscles=[
            MuscleVolume(
                muscle=m,
                weekly=weekly[m],
                target_low=target_range(m, profile["experience"])[0],
                target_high=target_range(m, profile["experience"])[1],
            )
            for m in ALL_MUSCLES
        ],
        push_sets=push,
        pull_sets=pull,
    )


# ---------------------------------------------------------------- calendar


class CalendarDay(BaseModel):
    day: date
    status: str  # done | missed | skipped | rest | upcoming


@router.get("/calendar", response_model=list[CalendarDay])
async def calendar(
    today: date,
    weeks: int = Query(default=12, ge=1, le=52),
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[CalendarDay]:
    profile = await _profile(conn, user)
    start = monday_of(today) - timedelta(weeks=weeks - 1)
    end = monday_of(today) + timedelta(days=6)
    joined = await conn.fetchval("SELECT created_at::date FROM users WHERE id = $1", user.id)
    done = {
        r["day"]
        for r in await conn.fetch(
            "SELECT DISTINCT day FROM set_logs WHERE user_id = $1 AND day BETWEEN $2 AND $3",
            user.id,
            start,
            end,
        )
    }
    skipped = {
        r["day"]
        for r in await conn.fetch(
            """SELECT day FROM day_overrides WHERE user_id = $1 AND action = 'skip'
           AND day BETWEEN $2 AND $3""",
            user.id,
            start,
            end,
        )
    }
    days = []
    d = start
    while d <= end:
        if d in done:
            s = "done"
        elif d in skipped:
            s = "skipped"
        elif d.weekday() not in profile["training_days"]:
            s = "rest"
        elif d >= today:
            s = "upcoming"
        elif d < joined:
            s = "rest"  # before you started using the app
        else:
            s = "missed"
        days.append(CalendarDay(day=d, status=s))
        d += timedelta(days=1)
    return days


# ---------------------------------------------------------------- recovery map


class MuscleRecovery(BaseModel):
    muscle: str
    state: str  # fresh | recovering | fatigued
    last_trained: date | None


@router.get("/recovery", response_model=list[MuscleRecovery])
async def recovery(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[MuscleRecovery]:
    """Fatigued: 3+ hard sets today or yesterday, or sore today. Recovering: trained
    2 days ago. Fresh: otherwise. (48-72 hours is the usual recovery window.)"""
    by_day = _muscle_sets(await _sets(conn, user, today - timedelta(days=6), today))
    sore = (
        await conn.fetchval(
            "SELECT sore_areas FROM readiness_checkins WHERE user_id = $1 AND day = $2",
            user.id,
            today,
        )
        or []
    )
    sore_muscles = {m for a in sore for m in SORE_AREAS.get(a, ())}
    out = []
    for m in ALL_MUSCLES:
        trained = sorted(
            (d for d, ms in by_day.items() if ms.get(m, 0) >= HARD_SETS_FOR_FATIGUE), reverse=True
        )
        last = trained[0] if trained else None
        ago = (today - last).days if last else None
        if m in sore_muscles or (ago is not None and ago <= 1):
            state = "fatigued"
        elif ago == 2:
            state = "recovering"
        else:
            state = "fresh"
        out.append(MuscleRecovery(muscle=m, state=state, last_trained=last))
    return out


# ---------------------------------------------------------------- weekly summary


class WeeklySummary(BaseModel):
    week_start: date
    sessions_done: int
    sessions_planned: int
    sets: int
    sets_last_week: int
    prs: list[str]  # exercise names with a new best e1RM this week
    under_target: list[str]  # muscles below their weekly target last full week
    weight_change_kg: float | None
    lines: list[str]


@router.get("/summary", response_model=WeeklySummary)
async def weekly_summary(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> WeeklySummary:
    profile = await _profile(conn, user)
    lib = load_library()
    start = monday_of(today)
    last_start = start - timedelta(days=7)
    this_rows = await _sets(conn, user, start, start + timedelta(days=6))
    last_rows = await _sets(conn, user, last_start, start - timedelta(days=1))

    # PRs this week: best e1RM this week beats everything before this week.
    prs = []
    for ex_id in sorted({r["exercise_id"] for r in this_rows}):
        week_best = max(
            (
                v
                for r in this_rows
                if r["exercise_id"] == ex_id and (v := e1rm(r["weight_kg"], r["reps"]))
            ),
            default=None,
        )
        before = await conn.fetch(
            """SELECT weight_kg, reps FROM set_logs
               WHERE user_id = $1 AND exercise_id = $2 AND day < $3""",
            user.id,
            ex_id,
            start,
        )
        prior = max((v for r in before if (v := e1rm(r["weight_kg"], r["reps"]))), default=None)
        if week_best and prior and week_best > prior:
            prs.append(lib[ex_id].name)

    last_week = defaultdict(float)
    for muscles in _muscle_sets(last_rows).values():
        for m, v in muscles.items():
            last_week[m] += v
    focus = ["chest", "lats", "upper_back", "quads", "glutes", "hamstrings", "front_delts"]
    under = [
        m for m in focus if last_rows and last_week[m] < target_range(m, profile["experience"])[0]
    ]

    weights = await conn.fetch(
        """SELECT day, weight_kg FROM body_weights
           WHERE user_id = $1 AND day BETWEEN $2 AND $3 ORDER BY day""",
        user.id,
        last_start,
        today,
    )
    this_w = [r["weight_kg"] for r in weights if r["day"] >= start]
    last_w = [r["weight_kg"] for r in weights if r["day"] < start]
    change = (
        round(sum(this_w) / len(this_w) - sum(last_w) / len(last_w), 2)
        if this_w and last_w
        else None
    )

    done = len({r["day"] for r in this_rows})
    planned = len(profile["training_days"])
    lines = [f"{done} of {planned} sessions done this week."]
    if this_rows and last_rows:
        lines.append(f"{len(this_rows)} sets so far. Last week you did {len(last_rows)}.")
    if prs:
        lines.append("New records: " + ", ".join(prs) + ".")
    if under:
        lines.append(
            "Last week these were under target: "
            + ", ".join(_MUSCLE_NAMES.get(m, m).lower() for m in under)
            + ". Your plan tops them up where time allows."
        )
    if not this_rows:
        lines.append("No sets logged yet this week. Today is a good day to start.")
    return WeeklySummary(
        week_start=start,
        sessions_done=done,
        sessions_planned=planned,
        sets=len(this_rows),
        sets_last_week=len(last_rows),
        prs=prs,
        under_target=under,
        weight_change_kg=change,
        lines=lines,
    )


# ---------------------------------------------------------------- logged exercises


class LoggedExercise(BaseModel):
    exercise_id: str
    name: str
    sessions: int
    best_e1rm: float | None
    last_day: date


@router.get("/exercises", response_model=list[LoggedExercise])
async def logged_exercises(
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> list[LoggedExercise]:
    rows = await conn.fetch(
        """SELECT exercise_id, count(DISTINCT day) AS sessions, max(day) AS last_day
           FROM set_logs WHERE user_id = $1 GROUP BY exercise_id
           ORDER BY count(DISTINCT day) DESC, max(day) DESC""",
        user.id,
    )
    lib = load_library()
    out = []
    for r in rows:
        if r["exercise_id"] not in lib:
            continue
        sets = await conn.fetch(
            "SELECT weight_kg, reps FROM set_logs WHERE user_id = $1 AND exercise_id = $2",
            user.id,
            r["exercise_id"],
        )
        best = max((v for s in sets if (v := e1rm(s["weight_kg"], s["reps"]))), default=None)
        out.append(
            LoggedExercise(
                exercise_id=r["exercise_id"],
                name=lib[r["exercise_id"]].name,
                sessions=r["sessions"],
                best_e1rm=round(best, 1) if best else None,
                last_day=r["last_day"],
            )
        )
    return out
