"""Progression: what weight and reps to aim for next time, and personal records.

Double progression (the classic, simple method):
  1. Keep the weight and add reps until every set reaches the top of the rep range.
  2. Then add weight and start again from the bottom of the range.
  3. If you miss the bottom of the range two sessions in a row at the same weight,
     drop about 10% and build back up.

Estimated one-rep max (e1RM) uses the Epley formula:
    e1RM = weight * (1 + reps / 30)
It's reasonably accurate up to about 10-12 reps, so sets above 12 reps are not used
for e1RM or PRs.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.library import Exercise

LoadType = Literal["barbell_lower", "barbell_upper", "dumbbell", "machine_lower", "machine_upper"]
Units = Literal["metric", "imperial"]

KG_PER_LB = 0.45359237
MAX_E1RM_REPS = 12
MISSES_BEFORE_REDUCING = 2
REDUCTION = 0.10
LIGHT_FACTOR = 0.80
DELOAD_FACTOR = 0.90

# Smallest sensible jump, in the user's own units.
INCREMENT = {
    "metric": {
        "barbell_lower": 5.0,
        "barbell_upper": 2.5,
        "dumbbell": 2.0,
        "machine_lower": 5.0,
        "machine_upper": 2.5,
    },
    "imperial": {
        "barbell_lower": 10.0,
        "barbell_upper": 5.0,
        "dumbbell": 5.0,
        "machine_lower": 10.0,
        "machine_upper": 5.0,
    },
}
STEP = {"metric": 2.5, "imperial": 5.0}  # weights are rounded to plates you can load
DUMBBELL_STEP = {"metric": 2.0, "imperial": 5.0}

BARBELLS = {"barbell", "trap_bar", "smith_machine", "ez_bar"}
FREE_WEIGHTS = {"dumbbells", "kettlebells"}
LOWER_PATTERNS = {"squat", "hinge", "lunge", "knee_extension", "knee_flexion", "calf_raise"}


def e1rm(weight_kg: float, reps: int) -> float | None:
    """Estimated one-rep max (Epley). None when it can't be estimated reliably."""
    if weight_kg <= 0 or reps < 1 or reps > MAX_E1RM_REPS:
        return None
    if reps == 1:
        return weight_kg
    return weight_kg * (1 + reps / 30)


def load_type(exercise: Exercise, equipment: frozenset[str]) -> LoadType | None:
    """How this exercise is loaded with the user's gear. None = bodyweight or bands
    (progress with reps, not plates)."""
    options = [set(o) for o in exercise.equipment if set(o) <= equipment and o]
    gear = set().union(*options) if options else set()
    lower = exercise.pattern in LOWER_PATTERNS
    if gear & BARBELLS:
        return "barbell_lower" if lower else "barbell_upper"
    if gear & FREE_WEIGHTS:
        return "dumbbell"
    if gear - {
        "resistance_bands",
        "suspension_trainer",
        "flat_bench",
        "adjustable_bench",
        "plyo_box",
        "pull_up_bar",
        "dip_station",
        "ab_wheel",
    }:
        return "machine_lower" if lower else "machine_upper"
    return None


def _to_units(kg: float, units: Units) -> float:
    return kg if units == "metric" else kg / KG_PER_LB


def _to_kg(value: float, units: Units) -> float:
    return value if units == "metric" else value * KG_PER_LB


def round_weight(kg: float, units: Units, kind: LoadType, *, down: bool = False) -> float:
    """Round to a loadable weight in the user's units; returns kilograms."""
    step = DUMBBELL_STEP[units] if kind == "dumbbell" else STEP[units]
    value = _to_units(kg, units) / step
    rounded = (int(value) if down else round(value)) * step
    return round(_to_kg(max(rounded, 0.0), units), 6)


@dataclass(frozen=True)
class LoggedSet:
    weight_kg: float
    reps: int
    rir: int | None = None


@dataclass(frozen=True)
class Session:
    day: date
    sets: tuple[LoggedSet, ...]


@dataclass(frozen=True)
class Target:
    weight_kg: float | None  # None: no history, or bodyweight
    reps: int  # aim for at least this many reps on each set
    reason: str
    change: Literal["first", "increase", "hold", "more_reps", "reduce", "light", "deload"]


def _top_sets(s: Session) -> tuple[float, list[LoggedSet]]:
    top = max(x.weight_kg for x in s.sets)
    return top, [x for x in s.sets if x.weight_kg == top]


def next_target(
    history: list[Session],
    rep_range: tuple[int, int],
    load: LoadType | None,
    units: Units,
    *,
    rir: int,
    light: bool = False,
    deload: bool = False,
) -> Target:
    """Target for the next session. `history` is newest first."""
    lo, hi = rep_range
    history = [s for s in history if s.sets]
    if not history:
        return Target(
            None,
            lo,
            f"First time: pick a weight you could lift about {lo + rir} times, "
            f"and stop at {lo} to {hi} reps.",
            "first",
        )

    weight, top = _top_sets(history[0])
    if load is None or weight <= 0:  # bodyweight or bands: progress with reps
        best = min(x.reps for x in top)
        goal = min(hi, best + 1) if best < hi else hi
        why = (
            f"You reached {hi} reps on every set: make it harder (slower lowering, a pause, "
            "or a harder variation)."
            if best >= hi
            else f"Aim for {goal} reps on each set."
        )
        return Target(None, goal, why, "more_reps")

    if all(x.reps >= hi for x in top):
        inc = INCREMENT[units][load]
        new = round_weight(weight + _to_kg(inc, units), units, load)
        target = Target(new, lo, f"You hit {hi} reps on every set: add weight.", "increase")
    else:
        misses = 0
        for s in history:
            w, t = _top_sets(s)
            if w == weight and any(x.reps < lo for x in t):
                misses += 1
            else:
                break
        if misses >= MISSES_BEFORE_REDUCING:
            new = round_weight(weight * (1 - REDUCTION), units, load, down=True)
            target = Target(
                new,
                lo,
                f"Missed {lo} reps {misses} sessions in a row: drop a little and build back up.",
                "reduce",
            )
        elif misses == 1:
            target = Target(weight, lo, f"Stay at this weight and aim for {lo}+ reps.", "hold")
        else:
            goal = min(hi, min(x.reps for x in top) + 1)
            target = Target(weight, goal, f"Same weight, aim for {goal} reps.", "more_reps")

    if light and target.weight_kg:
        return Target(
            round_weight(target.weight_kg * LIGHT_FACTOR, units, load, down=True),
            lo,
            "Light today: about 80% of your working weight.",
            "light",
        )
    if deload and target.weight_kg:
        return Target(
            round_weight(target.weight_kg * DELOAD_FACTOR, units, load, down=True),
            lo,
            "Deload week: a bit lighter, fewer sets.",
            "deload",
        )
    return target


def best_e1rm(sets: list[LoggedSet]) -> float | None:
    values = [v for s in sets if (v := e1rm(s.weight_kg, s.reps)) is not None]
    return max(values) if values else None


def is_pr(new: LoggedSet, previous: list[LoggedSet]) -> bool:
    """A personal record: this set's e1RM beats every earlier set's. The very first
    set of an exercise isn't a PR (there's nothing to beat yet)."""
    value = e1rm(new.weight_kg, new.reps)
    best = best_e1rm(previous)
    return value is not None and best is not None and value > best + 1e-9
