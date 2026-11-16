"""What the coach knows about the user: their real data, gathered from the same
endpoints the app uses, in the user's units.

Sent to an AI provider, so it holds no email, no name, no exact birth date, and no
free-text notes the user typed elsewhere: only training numbers and settings.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import asyncpg
from fastapi import HTTPException

from app.api.activities import activity_today, activity_week
from app.api.body import summary as body_summary
from app.api.exercises import _context as exercise_context
from app.api.plan import get_week
from app.api.stats import logged_exercises, recovery, volume, weekly_summary
from app.api.training import training_today
from app.auth.deps import CurrentUser
from app.catalog import MUSCLES
from app.library import load_library

KG_PER_LB = 0.45359237
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MUSCLE_NAMES = {m.id: m.name for m in MUSCLES}


@dataclass
class Today:
    """Facts the action checks need (see actions.py)."""

    day: date
    status: str  # planned | rest | skipped
    session_key: str | None
    session_name: str | None
    swapped: bool
    minutes: int
    logged_sets: int
    stop: bool
    exercise_ids: list[str]
    place: str | None = None  # where they train today, when not the active gym


@dataclass
class CoachContext:
    units: str  # kg | lb
    data: dict  # what the model sees
    today: Today
    sessions: dict[str, str]  # session key -> name, for swaps
    equipment: frozenset[str]
    injured: frozenset[str]
    preferences: dict[str, str]  # exercise id -> favorite | hidden
    names: dict[str, str] = field(default_factory=dict)  # exercise id -> name


def weight(kg: float | None, units: str) -> float | None:
    if kg is None:
        return None
    return round(kg if units == "kg" else kg / KG_PER_LB, 1)


def fmt_weight(kg: float | None, units: str) -> str:
    if not kg:
        return "bodyweight"
    w = weight(kg, units)
    return f"{w:g} {units}"


async def build(conn: asyncpg.Connection, user: CurrentUser, today: date) -> CoachContext:
    profile = await conn.fetchrow("SELECT * FROM profiles WHERE user_id = $1", user.id)
    if profile is None:
        raise HTTPException(404, "Set up your profile first")
    units = "kg" if profile["unit_system"] == "metric" else "lb"
    library = load_library()
    ex_ctx = await exercise_context(conn, user)

    t = await training_today(today=today, minutes=None, user=user, conn=conn)
    week = await get_week(today=today, day=None, user=user, conn=conn)
    summary = await weekly_summary(today=today, user=user, conn=conn)
    rec = await recovery(today=today, user=user, conn=conn)
    lifts = await logged_exercises(user=user, conn=conn)
    body = await body_summary(today=today, user=user, conn=conn)
    cardio_week = await activity_week(today=today, user=user, conn=conn)
    cardio_today = await activity_today(today=today, user=user, conn=conn)
    vol = await volume(today=today, weeks=2, user=user, conn=conn)

    day = t.day
    names = {e.exercise_id: e.name for e in day.exercises}
    plan_exercises = []
    for e, x in zip(day.exercises, t.exercises, strict=True):
        target = x.target
        plan_exercises.append(
            {
                "id": e.exercise_id,
                "name": e.name,
                "main_lift": e.kind == "main",
                "sets": e.sets,
                "reps": f"{e.reps[0]}-{e.reps[1]}",
                "reps_in_reserve": e.rir,
                "rest_seconds": e.rest_seconds,
                "light_today": e.light,
                "target": (
                    f"{fmt_weight(target.weight_kg, units)} x {target.reps}+ reps"
                    if target.weight_kg
                    else f"{target.reps}+ reps"
                ),
                "target_reason": target.reason,
                "logged_today": [
                    f"{fmt_weight(s.weight_kg, units)} x {s.reps}" + (" (record)" if s.pr else "")
                    for s in x.logged
                ],
            }
        )

    age = today.year - profile["birth_year"]
    body_data = {
        "latest_weight": weight(body.latest_weight_kg, units),
        "trend_weight": weight(body.trend_kg, units),
        "rate_per_week": weight(body.rate_kg_per_week, units),
        "bmi": body.bmi,
        "goal_timeline": body.weight_projection.message if body.weight_projection else None,
        "body_fat_timeline": (
            body.body_fat_projection.message if body.body_fat_projection else None
        ),
        "warnings": body.advice,
        "weigh_ins_last_4_weeks": sum(
            1 for w in body.weights if w.day >= today - timedelta(days=28)
        ),
    }

    data = {
        "today": f"{today.isoformat()} ({WEEKDAYS[today.weekday()]})",
        "units": units,
        "profile": {
            "age": age,
            "sex": profile["sex"],
            "height_cm": round(profile["height_cm"]),
            "weight": weight(profile["weight_kg"], units),
            "goal": profile["goal"],
            "target_weight": weight(profile["target_weight_kg"], units),
            "target_body_fat_pct": profile["target_body_fat_pct"],
            "experience": profile["experience"],
            "training_days": [WEEKDAYS[d] for d in sorted(profile["training_days"])],
            "session_minutes": profile["session_minutes"],
            "injury_areas": list(profile["injury_areas"] or []),
        },
        "split": {"name": week.split.name, "sessions": [s.name for s in week.split.sessions]},
        "today_plan": {
            "status": day.status,
            "session": day.session_name,
            "training_at": day.place or "their usual gym",
            "changed_by_user": day.swapped or day.status == "skipped",
            "minutes": day.minutes,
            "deload_week": t.deload,
            "notes": day.notes,
            "exercises": plan_exercises,
            "sets_logged_today": day.logged_sets,
        },
        "check_in_today": (
            {
                "verdict": t.readiness.verdict,
                "score_out_of_100": t.readiness.score,
                "messages": t.readiness.messages,
                "sore_areas": t.readiness.sore_areas,
                "avoid_areas": t.readiness.avoid_areas,
            }
            if t.readiness
            else None
        ),
        "this_week": [
            {
                "date": d.date.isoformat(),
                "day": WEEKDAYS[d.date.weekday()],
                "status": d.status,
                "session": d.session_name,
                "sets_logged": d.logged_sets,
            }
            for d in week.days
        ],
        "week_notes": week.notes,
        "progress_this_week": {
            "summary": summary.lines,
            "sessions_done": summary.sessions_done,
            "sessions_planned": summary.sessions_planned,
            "new_records": summary.prs,
            "muscles_under_target_last_week": [
                MUSCLE_NAMES.get(m, m) for m in summary.under_target
            ],
        },
        "sets_per_muscle": {
            "note": "hard sets; a muscle that only assists counts half; target is per week",
            "push_vs_pull_this_week": f"{vol.push_sets} push, {vol.pull_sets} pull",
            "muscles": [
                {
                    "muscle": MUSCLE_NAMES.get(v.muscle, v.muscle),
                    "this_week_so_far": v.weekly[-1],
                    "last_week": v.weekly[-2] if len(v.weekly) > 1 else None,
                    "weekly_target": f"{v.target_low}-{v.target_high}",
                }
                for v in vol.muscles
            ],
        },
        "recovery": {
            "needs_rest": [
                MUSCLE_NAMES.get(r.muscle, r.muscle) for r in rec if r.state == "fatigued"
            ],
            "recovering": [
                MUSCLE_NAMES.get(r.muscle, r.muscle) for r in rec if r.state == "recovering"
            ],
        },
        "strength_note": "all-time best estimated 1-rep max per lift: these are their records",
        "strength": [
            {
                "exercise": x.name,
                "sessions": x.sessions,
                "best_estimated_1rm": weight(x.best_e1rm, units),
                "last_done": x.last_day.isoformat(),
            }
            for x in lifts[:8]
        ],
        "body": body_data,
        "cardio": {
            "note": (
                "optional, on top of lifting; calories are estimates unless from a machine; "
                "logged on Today under Activity"
            ),
            "level": cardio_week.level,
            "weekly_target_minutes": cardio_week.target_minutes,
            "done_this_week_minutes": cardio_week.done_minutes,
            "logged_this_week": [
                f"{WEEKDAYS[a.day.weekday()]}: {a.name} {a.minutes:g} min, "
                f"{a.calories} kcal{' (estimate)' if a.calories_estimated else ''}"
                + (f" ({', '.join(a.item_names)})" if a.item_names else "")
                for a in cardio_week.activities
            ],
            "warm_up_today": cardio_today.warmup.text if cardio_today.warmup else None,
            "finisher_today": cardio_today.finisher.text if cardio_today.finisher else None,
            "rest_day_suggestion": cardio_today.rest_day,
            "cool_down_stretches_today": [x.name for x in cardio_today.cooldown],
        },
        "exercise_preferences": {
            "favorites": sorted(
                library[i].name for i, p in ex_ctx.prefs.items() if p == "favorite" and i in library
            ),
            "never_suggest": sorted(
                library[i].name for i, p in ex_ctx.prefs.items() if p == "hidden" and i in library
            ),
        },
    }

    return CoachContext(
        units=units,
        data=data,
        today=Today(
            day=today,
            status=day.status,
            session_key=day.session_key,
            session_name=day.session_name,
            swapped=day.swapped,
            minutes=day.minutes,
            logged_sets=day.logged_sets,
            stop=t.stop,
            exercise_ids=[e.exercise_id for e in day.exercises],
            place=day.place,
        ),
        sessions={s.key: s.name for s in week.split.sessions},
        equipment=ex_ctx.equipment,
        injured=ex_ctx.injured,
        preferences=dict(ex_ctx.prefs),
        names=names,
    )
