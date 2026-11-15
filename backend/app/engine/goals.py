"""Goal guardrails: check a goal for safety and give a realistic timeline.

The app never refuses a goal outright; it explains the risk and suggests a safer one.
Thresholds are deliberately conservative and documented here:

- Essential body fat is roughly 2-5% for men and 10-13% for women. Targets below
  8% (men) / 15% (women) are hard to sustain and can disrupt hormones, energy and
  recovery, so they get a warning.
- BMI below 18.5 is classed as underweight.
- Safe weight-change pace: losing 0.5-1.0% of bodyweight per week, gaining
  0.25-0.5% per week (faster gain is mostly fat).
"""

from dataclasses import dataclass
from math import ceil
from typing import Literal

Sex = Literal["male", "female"]
Goal = Literal["fat_loss", "muscle_gain", "recomposition", "strength"]
UnitSystem = Literal["metric", "imperial"]

KG_PER_LB = 0.45359237

MIN_SAFE_BODY_FAT_PCT: dict[str, float] = {"male": 8.0, "female": 15.0}
MIN_HEALTHY_BMI = 18.5
LOSS_RATE_PER_WEEK = (0.005, 0.010)  # fraction of current bodyweight (slowest, fastest)
GAIN_RATE_PER_WEEK = (0.0025, 0.005)
MEANINGFUL_CHANGE_KG = 0.5  # smaller differences count as "maintain"


@dataclass(frozen=True)
class Advice:
    code: str
    level: Literal["info", "warning"]
    message: str


def bmi(weight_kg: float, height_cm: float) -> float:
    meters = height_cm / 100
    return weight_kg / (meters * meters)


def format_weight(kg: float, units: UnitSystem, *, round_up: bool = False) -> str:
    """Show a weight in the user's units, e.g. "72.5 kg" or "160 lb"."""
    value, unit = (kg, "kg") if units == "metric" else (kg / KG_PER_LB, "lb")
    if round_up:
        return f"{ceil(value)} {unit}"
    return f"{round(value, 1):g} {unit}"


def safe_timeline_weeks(current_kg: float, target_kg: float) -> tuple[int, int] | None:
    """(fastest, slowest) number of weeks to reach target at a safe pace.

    None when the target is effectively the current weight.
    """
    delta = target_kg - current_kg
    if abs(delta) < MEANINGFUL_CHANGE_KG:
        return None
    slow_rate, fast_rate = LOSS_RATE_PER_WEEK if delta < 0 else GAIN_RATE_PER_WEEK
    fastest = ceil(abs(delta) / (fast_rate * current_kg))
    slowest = ceil(abs(delta) / (slow_rate * current_kg))
    return fastest, slowest


def assess_goal(
    *,
    sex: Sex,
    height_cm: float,
    weight_kg: float,
    goal: Goal,
    target_weight_kg: float | None = None,
    target_body_fat_pct: float | None = None,
    units: UnitSystem = "metric",
) -> list[Advice]:
    advice: list[Advice] = []

    if target_body_fat_pct is not None:
        floor = MIN_SAFE_BODY_FAT_PCT[sex]
        if target_body_fat_pct < floor:
            advice.append(
                Advice(
                    "body_fat_too_low",
                    "warning",
                    f"A target below {floor:g}% body fat is very hard to sustain and can "
                    "harm hormones, energy and recovery. A safer target is "
                    f"{floor + 2:g}% or higher.",
                )
            )

    if target_weight_kg is not None:
        target_bmi = bmi(target_weight_kg, height_cm)
        if target_bmi < MIN_HEALTHY_BMI:
            healthy_min_kg = MIN_HEALTHY_BMI * (height_cm / 100) ** 2
            advice.append(
                Advice(
                    "target_underweight",
                    "warning",
                    f"That target puts your BMI at {target_bmi:.1f}, below the healthy "
                    f"range (18.5+). Consider at least "
                    f"{format_weight(healthy_min_kg, units, round_up=True)}.",
                )
            )

        delta = target_weight_kg - weight_kg
        if goal == "fat_loss" and delta >= MEANINGFUL_CHANGE_KG:
            advice.append(
                Advice(
                    "goal_direction",
                    "info",
                    "Your goal is fat loss but your target weight is above your current "
                    "weight. Did you mean muscle gain or recomposition?",
                )
            )
        if goal == "muscle_gain" and delta <= -MEANINGFUL_CHANGE_KG:
            advice.append(
                Advice(
                    "goal_direction",
                    "info",
                    "Your goal is muscle gain but your target weight is below your "
                    "current weight. Did you mean fat loss or recomposition?",
                )
            )

        weeks = safe_timeline_weeks(weight_kg, target_weight_kg)
        if weeks is not None:
            fastest, slowest = weeks
            direction = "lose" if delta < 0 else "gain"
            advice.append(
                Advice(
                    "timeline",
                    "info",
                    f"To {direction} {format_weight(abs(delta), units)} at a safe pace takes about "
                    f"{fastest}-{slowest} weeks. Faster than that mostly costs muscle "
                    "(when losing) or adds fat (when gaining).",
                )
            )

    return advice
