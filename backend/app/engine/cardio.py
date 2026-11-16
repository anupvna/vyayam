"""Cardio and floor work: what can be logged, calorie estimates, weekly targets, and
the warm-up / finisher / rest-day suggestions shown on Today. Pure functions.

Nothing here is compulsory: lifting plans never depend on cardio. A short warm-up is
advised before lifting; everything else is a suggestion.

Calories, when the person doesn't enter the machine's number, are estimated:
- treadmill / walking / running with a speed: the ACSM metabolic equations
  (walking: VO2 = 0.1*S + 1.8*S*G + 3.5; running: VO2 = 0.2*S + 0.9*S*G + 3.5,
  S in m/min, G = incline as a fraction, VO2 in ml/kg/min);
- everything else: MET values per intensity, from the ranges in the Compendium of
  Physical Activities;
- kcal = MET x 3.5 x body weight (kg) / 200 per minute  (MET = VO2 / 3.5).
These are estimates (often +-20%), and the app labels them that way.
"""

from dataclasses import dataclass
from typing import Literal

Intensity = Literal["easy", "moderate", "hard"]
Field = Literal["speed", "incline", "level", "distance", "intensity", "items"]
Level = Literal["none", "light", "regular", "lots"]


@dataclass(frozen=True)
class Activity:
    id: str
    name: str
    group: Literal["machine", "outdoor", "floor", "other"]
    fields: tuple[Field, ...]
    met: tuple[float, float, float] | None  # easy, moderate, hard; None = from speed
    equipment: str | None = None  # gym equipment it needs, if any


ACTIVITIES: tuple[Activity, ...] = (
    Activity(
        "treadmill", "Treadmill", "machine", ("speed", "incline", "distance"), None, "treadmill"
    ),
    Activity(
        "stair_climber",
        "Stair climber",
        "machine",
        ("level", "intensity"),
        (5.0, 8.8, 10.0),
        "stair_climber",
    ),
    Activity(
        "bike",
        "Exercise bike",
        "machine",
        ("level", "distance", "intensity"),
        (4.0, 6.8, 8.8),
        "bike",
    ),
    Activity(
        "rower",
        "Rowing machine",
        "machine",
        ("level", "distance", "intensity"),
        (4.8, 7.0, 8.5),
        "rower",
    ),
    Activity(
        "elliptical", "Elliptical", "machine", ("level", "intensity"), (4.5, 5.5, 7.5), "elliptical"
    ),
    Activity("jump_rope", "Jump rope", "floor", ("intensity",), (8.8, 11.8, 12.3), "jump_rope"),
    Activity("mat_workout", "Mat workout", "floor", ("items", "intensity"), (3.0, 3.8, 5.0)),
    Activity("hiit", "Bodyweight HIIT", "floor", ("items", "intensity"), (6.0, 8.0, 10.0)),
    Activity("stretching", "Stretching / yoga", "floor", ("intensity",), (2.3, 2.5, 3.0)),
    Activity("walk", "Walk", "outdoor", ("speed", "distance"), None),
    Activity("run", "Run", "outdoor", ("speed", "distance"), None),
    Activity("cycling", "Cycling outside", "outdoor", ("distance", "intensity"), (5.8, 8.0, 10.0)),
    Activity("swim", "Swim", "outdoor", ("distance", "intensity"), (5.8, 8.3, 9.8)),
    Activity("sport", "Sport or other", "other", ("intensity",), (4.0, 6.0, 8.0)),
)
ACTIVITY_BY_ID = {a.id: a for a in ACTIVITIES}

# Moves for logging "I did this, this and this" on the floor, beyond the library's
# bodyweight exercises (which the API adds). Conditioning moves aren't strength
# exercises, so they live here rather than in the exercise library.
HIIT_MOVES: tuple[tuple[str, str], ...] = (
    ("burpee", "Burpees"),
    ("jumping_jacks", "Jumping jacks"),
    ("high_knees", "High knees"),
    ("skaters", "Skaters"),
    ("squat_thrust", "Squat thrusts"),
    ("plank_jacks", "Plank jacks"),
    ("butt_kicks", "Butt kicks"),
    ("shadow_boxing", "Shadow boxing"),
)

# Default speeds (km/h) when a walk or run is logged without one.
DEFAULT_SPEED = {"walk": 5.0, "run": 9.5, "treadmill": 5.5}
RUNNING_FROM_KMH = 8.0  # ACSM: walking equation below, running equation from here

LEVEL_MINUTES: dict[Level, int] = {"none": 0, "light": 75, "regular": 150, "lots": 225}
LEVEL_FOR_GOAL: dict[str, Level] = {
    "fat_loss": "regular",  # cardio adds to the energy deficit and to heart health
    "recomposition": "light",
    "muscle_gain": "light",  # mostly heart health; lots can cut into recovery
    "strength": "light",
}


def cardio_level(goal: str, chosen: str | None) -> Level:
    return chosen if chosen in LEVEL_MINUTES else LEVEL_FOR_GOAL.get(goal, "light")  # type: ignore[return-value]


def weekly_target(goal: str, chosen: str | None) -> int:
    """Minutes of cardio a week to aim for (on top of lifting)."""
    return LEVEL_MINUTES[cardio_level(goal, chosen)]


# ---------------------------------------------------------------- calories


def met_from_speed(kmh: float, incline_pct: float = 0.0) -> float:
    s = kmh * 1000 / 60  # m/min
    g = max(incline_pct, 0.0) / 100
    vo2 = (0.1 * s + 1.8 * s * g + 3.5) if kmh < RUNNING_FROM_KMH else (0.2 * s + 0.9 * s * g + 3.5)
    return vo2 / 3.5


def met_for(
    activity: str,
    *,
    intensity: Intensity = "moderate",
    speed_kmh: float | None = None,
    incline_pct: float | None = None,
) -> float:
    a = ACTIVITY_BY_ID[activity]
    if a.met is None or (speed_kmh and activity in ("walk", "run", "treadmill")):
        kmh = speed_kmh or DEFAULT_SPEED.get(activity, 5.0)
        return met_from_speed(kmh, incline_pct or 0.0)
    return a.met[("easy", "moderate", "hard").index(intensity)]


def estimate_calories(met: float, minutes: float, weight_kg: float) -> int:
    return round(met * 3.5 * weight_kg / 200 * minutes)


# ---------------------------------------------------------------- suggestions


@dataclass(frozen=True)
class Suggestion:
    activity: str
    minutes: int
    text: str


WARMUP_ORDER = ("treadmill", "bike", "elliptical", "rower", "stair_climber", "jump_rope")


def warmup(equipment: frozenset[str]) -> Suggestion:
    """Advised before every lifting session: 5 easy minutes, then light sets."""
    for a in WARMUP_ORDER:
        if ACTIVITY_BY_ID[a].equipment in equipment:
            name = ACTIVITY_BY_ID[a].name.lower()
            return Suggestion(
                a,
                5,
                f"5 minutes easy on the {name}, at a pace you could talk at. "
                "Then 1 or 2 light sets of your first exercise.",
            )
    return Suggestion(
        "hiit", 5, "5 minutes of marching on the spot, arm circles and easy jumping jacks. "
        "Then 1 or 2 light sets of your first exercise."
    )  # fmt: skip


def finisher(goal: str, level: Level, equipment: frozenset[str]) -> Suggestion | None:
    """An optional 8-10 minute finisher after lifting, for goals that benefit."""
    if level == "none" or (goal not in ("fat_loss", "recomposition") and level != "lots"):
        return None
    for a in ("bike", "rower", "elliptical", "treadmill", "stair_climber"):
        if ACTIVITY_BY_ID[a].equipment in equipment:
            name = ACTIVITY_BY_ID[a].name.lower()
            return Suggestion(
                a,
                10,
                f"Optional: 10 minutes of intervals on the {name}: "
                "30 seconds hard, 60 seconds easy.",
            )
    if "jump_rope" in equipment:
        return Suggestion(
            "jump_rope", 8, "Optional: 8 rounds of 30 seconds skipping, 30 seconds rest."
        )
    return Suggestion(
        "hiit", 9, "Optional: 3 rounds of 30 seconds each of burpees, mountain climbers and "
        "jump squats, with a minute's rest between rounds."
    )  # fmt: skip


def rest_day(level: Level, done: int, target: int) -> str | None:
    if level == "none":
        return None
    left = max(target - done, 0)
    if left == 0:
        return "You've hit this week's cardio already. A gentle walk still helps recovery."
    return (
        f"An easy 20 to 30 minutes of walking, cycling or the elliptical helps recovery "
        f"and counts toward this week's cardio ({done} of {target} minutes so far)."
    )
