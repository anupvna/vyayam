"""Changes the coach may propose. The model only suggests; the engine decides.

check() runs when the reply is made (invalid proposals are dropped) and again when the
user taps Apply (the plan may have changed since). apply() then uses the same endpoint
code as the rest of the app, so every rule those endpoints enforce still holds.
"""

from dataclasses import dataclass
from typing import Literal

import asyncpg
from pydantic import BaseModel, ConfigDict

from app.api.exercises import PreferenceIn, set_preference
from app.api.plan import (
    MAT_PLACE,
    PlaceIn,
    SwapIn,
    TodayIn,
    reset_place,
    restore_day,
    set_place,
    skip_day,
    swap_day,
)
from app.auth.deps import CurrentUser
from app.coach.context import CoachContext
from app.engine.alternatives import find_alternatives, is_available, is_safe
from app.library import load_library

ActionType = Literal[
    "skip_today",
    "swap_today",
    "shorten_today",
    "restore_today",
    "hide_exercise",
    "favorite_exercise",
    "train_at_home_today",
    "back_to_gym_today",
]
SHORTER = (30, 45)


class Action(BaseModel):
    """One proposal, as the model writes it (every field present; unused ones null)."""

    model_config = ConfigDict(extra="forbid")

    type: ActionType
    session_key: str | None = None
    minutes: int | None = None
    exercise_id: str | None = None


@dataclass(frozen=True)
class Checked:
    action: Action
    ok: bool
    label: str  # what the Apply button says
    reason: str  # why it was refused (empty when ok)


def _no(a: Action, reason: str) -> Checked:
    return Checked(a, False, "", reason)


def check(a: Action, ctx: CoachContext) -> Checked:
    t = ctx.today
    library = load_library()

    if a.type in ("skip_today", "swap_today", "shorten_today", "train_at_home_today"):
        if t.status == "rest":
            return _no(a, "today is a rest day")
        if t.stop:
            return _no(a, "today's check-in says no training")
    if a.type in ("skip_today", "swap_today", "train_at_home_today") and t.logged_sets:
        return _no(a, "sets are already logged today")

    if a.type == "skip_today":
        if t.status == "skipped":
            return _no(a, "today is already skipped")
        return Checked(a, True, "Skip today's workout", "")

    if a.type == "swap_today":
        if a.session_key not in ctx.sessions:
            return _no(a, f"{a.session_key!r} isn't a session in this split")
        if a.session_key == t.session_key and t.status == "planned":
            return _no(a, "that's already today's session")
        return Checked(a, True, f"Do {ctx.sessions[a.session_key]} today instead", "")

    if a.type == "shorten_today":
        if t.status != "planned":
            return _no(a, "there's no workout today to shorten")
        if a.minutes not in SHORTER:
            return _no(a, "sessions can be shortened to 30 or 45 minutes")
        if a.minutes >= t.minutes:
            return _no(a, f"today's session already fits {a.minutes} minutes")
        return Checked(a, True, f"Shorten today to {a.minutes} minutes", "")

    if a.type == "train_at_home_today":
        if t.status != "planned":
            return _no(a, "there's no workout today")
        if t.place == MAT_PLACE:
            return _no(a, "today is already set to home on a mat")
        return Checked(a, True, "Train at home on a mat today", "")

    if a.type == "back_to_gym_today":
        if t.place is None:
            return _no(a, "today is already at your usual gym")
        return Checked(a, True, "Back to your usual gym today", "")

    if a.type == "restore_today":
        if not (t.swapped or t.status == "skipped"):
            return _no(a, "today hasn't been changed")
        return Checked(a, True, "Undo today's change", "")

    # Exercise preferences
    ex = library.get(a.exercise_id or "")
    if ex is None:
        return _no(a, f"unknown exercise {a.exercise_id!r}")
    current = ctx.preferences.get(ex.id)

    if a.type == "favorite_exercise":
        if current == "favorite":
            return _no(a, "already a favorite")
        if not is_available(ex, ctx.equipment):
            return _no(a, "needs equipment the active gym doesn't have")
        if not is_safe(ex, ctx.injured):
            return _no(a, "loads an injured area")
        return Checked(a, True, f"Add {ex.name} to favorites", "")

    # hide_exercise
    if current == "hidden":
        return _no(a, "already hidden")
    hidden = frozenset(k for k, v in ctx.preferences.items() if v == "hidden") | {ex.id}
    alternatives = find_alternatives(
        ex,
        library.values(),
        equipment=ctx.equipment,
        injured=ctx.injured,
        hidden=hidden,
        favorites=frozenset(k for k, v in ctx.preferences.items() if v == "favorite"),
        limit=1,
    )
    if not alternatives:
        return _no(a, "nothing else at this gym trains the same thing")
    return Checked(a, True, f"Stop suggesting {ex.name} (e.g. {alternatives[0].name} instead)", "")


def check_all(actions: list[Action], ctx: CoachContext, limit: int = 2) -> list[Checked]:
    """Valid proposals only, without duplicates, at most `limit`."""
    seen: set[tuple] = set()
    out = []
    for a in actions:
        key = (a.type, a.session_key, a.minutes, a.exercise_id)
        if key in seen:
            continue
        seen.add(key)
        c = check(a, ctx)
        if c.ok:
            out.append(c)
    return out[:limit]


async def apply(a: Action, conn: asyncpg.Connection, user: CurrentUser, ctx: CoachContext) -> dict:
    """Make the change. Returns what the app should do next on screen."""
    t = ctx.today
    if a.type == "skip_today":
        await skip_day(day=t.day, body=TodayIn(today=t.day), user=user, conn=conn)
    elif a.type == "swap_today":
        await swap_day(
            day=t.day, body=SwapIn(session_key=a.session_key, today=t.day), user=user, conn=conn
        )
    elif a.type == "restore_today":
        await restore_day(day=t.day, user=user, conn=conn)
    elif a.type == "train_at_home_today":
        await set_place(day=t.day, body=PlaceIn(today=t.day, mat=True), user=user, conn=conn)
    elif a.type == "back_to_gym_today":
        await reset_place(day=t.day, user=user, conn=conn)
    elif a.type == "shorten_today":
        return {"minutes": a.minutes}  # a view setting: the Today screen applies it
    else:
        pref = "hidden" if a.type == "hide_exercise" else "favorite"
        await set_preference(
            exercise_id=a.exercise_id or "",
            body=PreferenceIn(preference=pref),
            user=user,
            conn=conn,
        )
    return {}
