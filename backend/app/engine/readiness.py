"""Daily readiness check-in and the safety layer.

The safety layer is deterministic and runs before anything else. It cannot be
overridden by the plan, by user settings, or (later) by the AI coach:

  - Red flags (chest pain, dizziness or fainting, unusual shortness of breath,
    sharp joint pain, numbness or tingling) -> stop training today and seek medical
    help. No workout is shown.
  - Pain in an area -> exercises loading that area are removed for today, with advice
    to rest it and to see a professional if it persists.

Readiness (sleep, energy, stress, soreness) adjusts the day: normal, lighter, or a
suggestion to rest. This is a training aid, not a diagnosis.
"""

from dataclasses import dataclass, field
from typing import Literal

RED_FLAGS: dict[str, str] = {
    "chest_pain": "Chest pain or pressure",
    "dizziness": "Dizziness or fainting",
    "shortness_of_breath": "Unusual shortness of breath",
    "sharp_joint_pain": "Sharp pain in a joint",
    "numbness": "Numbness or tingling",
}

# Coarse areas for muscle soreness, and which muscles they cover.
SORE_AREAS: dict[str, tuple[str, ...]] = {
    "chest": ("chest",),
    "back": ("lats", "upper_back", "lower_back", "traps"),
    "shoulders": ("front_delts", "side_delts", "rear_delts"),
    "arms": ("biceps", "triceps", "forearms"),
    "core": ("abs", "obliques"),
    "glutes": ("glutes",),
    "legs": ("quads", "hamstrings", "adductors", "calves"),
}

STOP_MESSAGE = (
    "These symptoms can be a sign of a medical problem. "
    "If you have chest pain, fainted, or are struggling to breathe, call emergency "
    "services (911 in the US) now. Otherwise, see a doctor before you train again."
)
PERSISTENT_PAIN_DAYS = 3  # check-ins with pain in the same area within 14 days

Verdict = Literal["stop", "rest", "lighter", "normal"]


@dataclass(frozen=True)
class CheckIn:
    sleep: int  # 1 (terrible) .. 5 (great)
    energy: int  # 1 (drained) .. 5 (great)
    stress: int  # 1 (calm) .. 5 (very stressed)
    sore_areas: frozenset[str] = frozenset()
    pain_areas: frozenset[str] = frozenset()  # body parts from the catalog
    red_flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Assessment:
    verdict: Verdict
    score: int  # 0..100
    messages: tuple[str, ...]
    avoid_areas: frozenset[str] = frozenset()  # body parts to keep out of today's plan
    sore_muscles: frozenset[str] = frozenset()  # keep these light today
    persistent_pain: tuple[str, ...] = field(default=())


def readiness_score(c: CheckIn) -> int:
    """0-100. Sleep and energy matter most; stress and soreness a little less."""
    score = (
        (c.sleep - 1) / 4 * 35
        + (c.energy - 1) / 4 * 35
        + (5 - c.stress) / 4 * 20
        + max(0, 10 - 4 * len(c.sore_areas))
    )
    return round(score)


def assess(c: CheckIn, pain_history: dict[str, int] | None = None) -> Assessment:
    """`pain_history`: area -> number of recent check-ins (last 14 days, including
    today) that reported pain there."""
    if c.red_flags:  # safety first, always
        return Assessment("stop", readiness_score(c), (STOP_MESSAGE,))

    score = readiness_score(c)
    messages: list[str] = []
    pain_history = pain_history or {}
    persistent = tuple(
        sorted(a for a in c.pain_areas if pain_history.get(a, 0) >= PERSISTENT_PAIN_DAYS)
    )

    if c.pain_areas:
        names = ", ".join(sorted(a.replace("_", " ") for a in c.pain_areas))
        messages.append(
            f"Pain in your {names}: exercises that load it are left out today. Rest it, "
            "and if it lasts more than a week or gets worse, see a doctor or physiotherapist."
        )
    if persistent:
        names = ", ".join(a.replace("_", " ") for a in persistent)
        messages.append(
            f"Your {names} has hurt on several days recently. Please get it checked by a "
            "qualified professional before training it again."
        )

    sore = frozenset(m for area in c.sore_areas for m in SORE_AREAS.get(area, ()))
    if score < 35:
        verdict: Verdict = "rest"
        messages.insert(
            0,
            "You're running low today. Rest is the best choice; if you still "
            "want to move, do the easy version.",
        )
    elif score < 60:
        verdict = "lighter"
        messages.insert(
            0,
            "Not your best day, so today is a bit lighter: one set fewer per "
            "exercise and a little further from failure.",
        )
    else:
        verdict = "normal"
    if sore and verdict != "rest":
        messages.append("Sore areas are kept light today.")
    return Assessment(verdict, score, tuple(messages), frozenset(c.pain_areas), sore, persistent)
