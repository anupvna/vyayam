"""Training splits: how a week of sessions is divided up.

A *session template* is a list of slots. A slot says what kind of movement goes there
("a horizontal push, main lift, 3 sets") rather than naming an exercise; the planner
then picks the best exercise for each slot from the user's gym, injuries and
favorites. That's why one split works in a full gym, a home gym or a hotel room.

A *split* is a cycle of session templates. Training days take sessions from the
cycle in order, so a 3-day week on a 4-session split simply continues where the last
week stopped.
"""

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["main", "accessory"]
Style = Literal["power", "hypertrophy"] | None

MAJOR_MUSCLES = frozenset(
    {"chest", "lats", "upper_back", "quads", "glutes", "hamstrings", "front_delts"}
)


@dataclass(frozen=True)
class Slot:
    patterns: tuple[str, ...]  # preferred movement patterns, best first
    kind: Kind
    muscles: tuple[str, ...]  # fallback: any exercise working these
    sets: int = 3


@dataclass(frozen=True)
class SessionTemplate:
    key: str
    name: str
    focus: tuple[str, ...]  # muscles, for display
    slots: tuple[Slot, ...]
    style: Style = None


def _s(patterns: str, kind: Kind, muscles: str, sets: int = 3) -> Slot:
    return Slot(tuple(patterns.split()), kind, tuple(muscles.split()), sets)


# Shorthands for common slots.
SQUAT_MAIN = _s("squat", "main", "quads glutes")
HINGE_MAIN = _s("hinge", "main", "hamstrings glutes")
HINGE_ACC = _s("hinge", "accessory", "hamstrings glutes")
LUNGE = _s("lunge squat", "accessory", "quads glutes", 2)
HPUSH_MAIN = _s("horizontal_push", "main", "chest")
HPUSH_ACC = _s("horizontal_push", "accessory", "chest")
VPUSH_MAIN = _s("vertical_push", "main", "front_delts")
VPUSH_ACC = _s("vertical_push", "accessory", "front_delts")
HPULL_MAIN = _s("horizontal_pull", "main", "lats upper_back")
HPULL_ACC = _s("horizontal_pull", "accessory", "lats upper_back")
VPULL_MAIN = _s("vertical_pull", "main", "lats")
VPULL_ACC = _s("vertical_pull", "accessory", "lats")
FLY = _s("chest_fly", "accessory", "chest", 2)
LATERAL = _s("lateral_raise", "accessory", "side_delts", 2)
REAR = _s("rear_delt_fly", "accessory", "rear_delts", 2)
CURL = _s("elbow_flexion", "accessory", "biceps", 2)
TRICEPS = _s("elbow_extension", "accessory", "triceps", 2)
KNEE_EXT = _s("knee_extension lunge", "accessory", "quads", 2)
KNEE_FLEX = _s("knee_flexion hinge", "accessory", "hamstrings", 2)
CALF = _s("calf_raise", "accessory", "calves", 3)
CORE = _s("core", "accessory", "abs", 2)
SHRUG = _s("shrug carry", "accessory", "traps", 2)


def _t(key: str, name: str, focus: str, *slots: Slot, style: Style = None) -> SessionTemplate:
    return SessionTemplate(key, name, tuple(focus.split()), slots, style)


TEMPLATES: dict[str, SessionTemplate] = {
    t.key: t
    for t in (
        _t(
            "full_a",
            "Full body A",
            "quads chest lats",
            SQUAT_MAIN,
            HPUSH_MAIN,
            HPULL_ACC,
            HINGE_ACC,
            LATERAL,
            CORE,
        ),
        _t(
            "full_b",
            "Full body B",
            "glutes front_delts lats",
            HINGE_MAIN,
            VPUSH_MAIN,
            VPULL_ACC,
            LUNGE,
            CURL,
            TRICEPS,
        ),
        _t(
            "upper_a",
            "Upper A",
            "chest lats front_delts",
            HPUSH_MAIN,
            HPULL_MAIN,
            VPUSH_ACC,
            VPULL_ACC,
            LATERAL,
            CURL,
            TRICEPS,
        ),
        _t(
            "upper_b",
            "Upper B",
            "lats front_delts chest",
            VPULL_MAIN,
            VPUSH_MAIN,
            HPUSH_ACC,
            HPULL_ACC,
            REAR,
            CURL,
            TRICEPS,
        ),
        _t(
            "lower_a",
            "Lower A",
            "quads hamstrings glutes",
            SQUAT_MAIN,
            HINGE_ACC,
            LUNGE,
            KNEE_FLEX,
            CALF,
            CORE,
        ),
        _t(
            "lower_b",
            "Lower B",
            "glutes hamstrings quads",
            HINGE_MAIN,
            _s("squat", "accessory", "quads glutes"),
            KNEE_EXT,
            KNEE_FLEX,
            CALF,
            CORE,
        ),
        _t(
            "upper_power",
            "Upper power",
            "chest lats front_delts",
            HPUSH_MAIN,
            HPULL_MAIN,
            VPUSH_MAIN,
            VPULL_ACC,
            CURL,
            TRICEPS,
            style="power",
        ),
        _t(
            "lower_power",
            "Lower power",
            "quads glutes hamstrings",
            SQUAT_MAIN,
            HINGE_MAIN,
            LUNGE,
            CALF,
            CORE,
            style="power",
        ),
        _t(
            "upper_hyp",
            "Upper volume",
            "chest lats side_delts",
            HPUSH_ACC,
            HPULL_ACC,
            FLY,
            VPULL_ACC,
            LATERAL,
            CURL,
            TRICEPS,
            style="hypertrophy",
        ),
        _t(
            "lower_hyp",
            "Lower volume",
            "quads hamstrings calves",
            _s("squat", "accessory", "quads glutes"),
            HINGE_ACC,
            KNEE_EXT,
            KNEE_FLEX,
            CALF,
            style="hypertrophy",
        ),
        _t(
            "push",
            "Push",
            "chest front_delts triceps",
            HPUSH_MAIN,
            VPUSH_ACC,
            HPUSH_ACC,
            FLY,
            LATERAL,
            TRICEPS,
        ),
        _t(
            "pull",
            "Pull",
            "lats upper_back biceps",
            VPULL_MAIN,
            HPULL_MAIN,
            HPULL_ACC,
            REAR,
            CURL,
            SHRUG,
        ),
        _t(
            "legs",
            "Legs",
            "quads glutes hamstrings",
            SQUAT_MAIN,
            HINGE_ACC,
            LUNGE,
            KNEE_EXT,
            KNEE_FLEX,
            CALF,
            CORE,
        ),
        _t(
            "chest",
            "Chest",
            "chest",
            HPUSH_MAIN,
            HPUSH_ACC,
            _s("horizontal_push", "accessory", "chest triceps"),
            FLY,
            CORE,
        ),
        _t(
            "back",
            "Back",
            "lats upper_back traps",
            VPULL_MAIN,
            HPULL_MAIN,
            HPULL_ACC,
            VPULL_ACC,
            SHRUG,
        ),
        _t(
            "shoulders",
            "Shoulders",
            "front_delts side_delts rear_delts",
            VPUSH_MAIN,
            LATERAL,
            _s("lateral_raise", "accessory", "side_delts"),
            REAR,
            SHRUG,
        ),
        _t(
            "arms",
            "Arms",
            "biceps triceps forearms",
            CURL,
            TRICEPS,
            _s("elbow_flexion", "accessory", "biceps forearms"),
            _s("elbow_extension", "accessory", "triceps"),
            CORE,
        ),
        _t(
            "chest_triceps",
            "Chest and triceps",
            "chest triceps",
            HPUSH_MAIN,
            HPUSH_ACC,
            FLY,
            TRICEPS,
            _s("elbow_extension", "accessory", "triceps"),
        ),
        _t(
            "back_biceps",
            "Back and biceps",
            "lats upper_back biceps",
            VPULL_MAIN,
            HPULL_MAIN,
            HPULL_ACC,
            CURL,
            _s("elbow_flexion", "accessory", "biceps forearms"),
        ),
        _t(
            "legs_shoulders",
            "Legs and shoulders",
            "quads glutes front_delts",
            SQUAT_MAIN,
            HINGE_ACC,
            LUNGE,
            CALF,
            VPUSH_ACC,
            LATERAL,
        ),
        _t(
            "chest_back",
            "Chest and back",
            "chest lats upper_back",
            HPUSH_MAIN,
            HPULL_MAIN,
            HPUSH_ACC,
            VPULL_ACC,
            FLY,
        ),
        _t(
            "shoulders_arms",
            "Shoulders and arms",
            "front_delts biceps triceps",
            VPUSH_MAIN,
            LATERAL,
            REAR,
            CURL,
            TRICEPS,
        ),
        _t(
            "torso",
            "Torso",
            "chest lats front_delts",
            HPUSH_MAIN,
            HPULL_MAIN,
            VPUSH_ACC,
            VPULL_ACC,
            LATERAL,
            CORE,
        ),
        _t(
            "limbs",
            "Limbs",
            "quads hamstrings biceps triceps",
            SQUAT_MAIN,
            HINGE_ACC,
            LUNGE,
            CALF,
            CURL,
            TRICEPS,
        ),
    )
}


@dataclass(frozen=True)
class Split:
    id: str
    name: str
    blurb: str
    cycle: tuple[str, ...]  # session template keys, in order
    designed_for: tuple[int, ...]  # days per week it's built for
    tags: tuple[str, ...] = field(default=())


SPLITS: dict[str, Split] = {
    s.id: s
    for s in (
        Split(
            "full_body",
            "Full body",
            "Every session trains the whole body. "
            "Best for 2 or 3 days a week and for newer lifters.",
            ("full_a", "full_b"),
            (2, 3),
        ),
        Split(
            "upper_lower",
            "Upper / lower",
            "Alternate upper-body and lower-body days. Each muscle twice a week on 4 days.",
            ("upper_a", "lower_a", "upper_b", "lower_b"),
            (4,),
        ),
        Split(
            "ppl",
            "Push / pull / legs",
            "Pressing muscles, pulling muscles, then legs. Great on 3 or 6 days.",
            ("push", "pull", "legs"),
            (3, 6),
        ),
        Split(
            "ulppl",
            "Upper / lower + push / pull / legs",
            "A 5-day hybrid: one upper/lower pair plus a PPL round.",
            ("upper_a", "lower_a", "push", "pull", "legs"),
            (5,),
        ),
        Split(
            "phul",
            "Power / hypertrophy (PHUL)",
            "Two heavy days for strength and two higher-rep days for size.",
            ("upper_power", "lower_power", "upper_hyp", "lower_hyp"),
            (4,),
        ),
        Split(
            "bro",
            "Body-part split",
            "Chest, back, legs, shoulders, arms: one big day per muscle group.",
            ("chest", "back", "legs", "shoulders", "arms"),
            (5,),
        ),
        Split(
            "chest_back_legs",
            "Chest+triceps / back+biceps / legs+shoulders",
            "Classic gym pairing of a big muscle with the small one that helps it.",
            ("chest_triceps", "back_biceps", "legs_shoulders"),
            (3, 6),
        ),
        Split(
            "arnold",
            "Arnold split",
            "Chest and back together, then shoulders and arms, then legs.",
            ("chest_back", "shoulders_arms", "legs"),
            (3, 6),
        ),
        Split(
            "torso_limbs",
            "Torso / limbs",
            "Torso one day, legs and arms the next.",
            ("torso", "limbs"),
            (2, 4),
        ),
    )
}


def recommend_split(days: list[int], experience: str, goal: str) -> tuple[str, str]:
    """(split id, one-sentence reason). `days` are weekdays 0=Mon..6=Sun."""
    n = len(days)
    consecutive = any((d + 1) % 7 in days for d in days)
    if n <= 2:
        return "full_body", (
            f"With {n} day{'s' if n > 1 else ''} a week, training everything each session "
            "hits every muscle often enough to grow."
        )
    if n == 3:
        if experience == "beginner" or not consecutive:
            return "full_body", (
                "Three full-body sessions train each muscle three times a week, the fastest "
                "way for most people to build strength and size."
            )
        return "ppl", (
            "Your days are back to back, so push / pull / legs keeps each muscle rested "
            "between sessions."
        )
    if n == 4:
        if goal == "strength" and experience != "beginner":
            return "phul", "Four days and a strength goal: two heavy days plus two volume days."
        return "upper_lower", "Four days fits upper / lower: every muscle twice a week."
    if n == 5:
        return "ulppl", (
            "Five days: an upper / lower pair plus push / pull / legs trains each muscle "
            "about twice a week."
        )
    return "ppl", "Six days: push / pull / legs twice, each muscle twice a week."


# Which movement patterns train a muscle, best first. Used for freestyle sessions
# ("today I want chest and arms") and custom splits.
MUSCLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "chest": ("horizontal_push", "chest_fly"),
    "front_delts": ("vertical_push",),
    "side_delts": ("lateral_raise",),
    "rear_delts": ("rear_delt_fly",),
    "lats": ("vertical_pull", "horizontal_pull"),
    "upper_back": ("horizontal_pull", "rear_delt_fly"),
    "traps": ("shrug", "carry"),
    "biceps": ("elbow_flexion",),
    "triceps": ("elbow_extension",),
    "forearms": ("carry", "elbow_flexion"),
    "abs": ("core",),
    "obliques": ("core",),
    "lower_back": ("hinge",),
    "glutes": ("hinge", "lunge"),
    "quads": ("squat", "lunge", "knee_extension"),
    "hamstrings": ("hinge", "knee_flexion"),
    "adductors": ("squat", "lunge"),
    "calves": ("calf_raise",),
}


def template_from_muscles(key: str, name: str, muscles: list[str]) -> SessionTemplate:
    """Build a session for chosen muscles: big muscles get a main lift plus an
    accessory, small muscles one accessory. Order: big muscles first."""
    ordered = sorted(
        dict.fromkeys(muscles), key=lambda m: (m not in MAJOR_MUSCLES, muscles.index(m))
    )
    mains: list[Slot] = []
    accessories: list[Slot] = []
    for m in ordered:
        patterns = MUSCLE_PATTERNS[m]
        if m in MAJOR_MUSCLES:
            mains.append(Slot((patterns[0],), "main", (m,), 3))
            accessories.append(Slot(patterns[1:] or patterns, "accessory", (m,), 3))
        else:
            accessories.append(Slot(patterns, "accessory", (m,), 3))
    slots = mains + accessories  # heavy lifts first, while you're fresh
    return SessionTemplate(key, name, tuple(ordered), tuple(slots))
