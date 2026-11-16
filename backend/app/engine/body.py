"""Body calculations: trend weight, body fat estimates, rate of change, and a goal
date range. Pure functions, unit-tested against worked examples.

- Trend weight: an exponential moving average (EMA) of daily weigh-ins. Day-to-day
  weight swings by 1-2 kg with water and food; the trend shows the real direction.
  Each day the trend moves 10% of the way toward the new weigh-in. When days are
  missed, the step is scaled so a gap of n days counts like n days of smoothing:
      alpha_effective = 1 - (1 - 0.1) ** days_since_last
- Body fat (US Navy tape method, metric form, all lengths in cm):
      men:   495 / (1.0324  - 0.19077 * log10(waist - neck)       + 0.15456 * log10(height)) - 450
      women: 495 / (1.29579 - 0.35004 * log10(waist + hip - neck) + 0.22100 * log10(height)) - 450
  Typical error is around +-3 to 4 percentage points against DEXA, so it's always
  shown as an estimate. Its strength is tracking change with consistent measuring.
- Rate: least-squares slope of the trend over the last 3 weeks, in kg per week.
- Projection: a date *range*, from 75% to 125% of the current pace, because no
  single date is honest. Only when the trend is actually heading toward the target.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from math import log10
from typing import Literal

ALPHA = 0.1
RATE_WINDOW_DAYS = 21
MIN_RATE_POINTS = 4
MIN_RATE_SPAN_DAYS = 7
FLAT_KG_PER_WEEK = 0.05  # slower than this counts as "holding steady"
SAFE_LOSS_PCT = 1.0  # % of bodyweight per week
SAFE_GAIN_PCT = 0.5


def trend_weights(points: list[tuple[date, float]]) -> list[tuple[date, float, float]]:
    """(day, weight, trend) for weigh-ins sorted by day."""
    out: list[tuple[date, float, float]] = []
    trend: float | None = None
    last: date | None = None
    for day, w in sorted(points):
        if trend is None or last is None:
            trend = w
        else:
            gap = max(1, (day - last).days)
            a = 1 - (1 - ALPHA) ** gap
            trend = trend + a * (w - trend)
        out.append((day, w, trend))
        last = day
    return out


def navy_body_fat(
    sex: str, height_cm: float, neck_cm: float, waist_cm: float, hips_cm: float | None = None
) -> float | None:
    """US Navy estimate in %, or None if the measurements can't give a valid result."""
    try:
        if sex == "male":
            if waist_cm <= neck_cm:
                return None
            pct = (
                495 / (1.0324 - 0.19077 * log10(waist_cm - neck_cm) + 0.15456 * log10(height_cm))
                - 450
            )
        else:
            if hips_cm is None or waist_cm + hips_cm <= neck_cm:
                return None
            pct = (
                495
                / (
                    1.29579
                    - 0.35004 * log10(waist_cm + hips_cm - neck_cm)
                    + 0.22100 * log10(height_cm)
                )
                - 450
            )
    except (ValueError, ZeroDivisionError):
        return None
    return round(pct, 1) if 2 <= pct <= 60 else None


def slope_per_week(points: list[tuple[date, float]]) -> float | None:
    """Least-squares slope in units per week, or None if there isn't enough data."""
    if len(points) < MIN_RATE_POINTS:
        return None
    first = points[0][0]
    xs = [(d - first).days for d, _ in points]
    if xs[-1] - xs[0] < MIN_RATE_SPAN_DAYS:
        return None
    ys = [v for _, v in points]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx * 7


def recent_rate(trend: list[tuple[date, float, float]], today: date) -> float | None:
    window = [(d, t) for d, _, t in trend if d > today - timedelta(days=RATE_WINDOW_DAYS)]
    return slope_per_week(window)


@dataclass(frozen=True)
class Projection:
    status: Literal["reached", "on_track", "wrong_way", "flat", "not_enough_data"]
    message: str
    earliest: date | None = None
    latest: date | None = None


def project(
    current: float, target: float, rate_per_week: float | None, today: date, unit: str = "kg"
) -> Projection:
    """When will `current` reach `target` at the recent rate? Works for weight (kg)
    and body fat (%)."""
    gap = target - current
    if abs(gap) < 0.5:
        return Projection("reached", "You're at your target. Nice work: now hold it.")
    if rate_per_week is None:
        return Projection(
            "not_enough_data",
            "Log a few more weigh-ins over at least a week to see a timeline."
            if unit == "kg"
            else "Measure a few more times (every week or two) to see a timeline.",
        )
    if abs(rate_per_week) < FLAT_KG_PER_WEEK:
        return Projection("flat", "You're holding steady, so there's no timeline yet.")
    if (gap > 0) != (rate_per_week > 0):
        return Projection(
            "wrong_way",
            "Your trend is moving away from your target right now.",
        )
    weeks = gap / rate_per_week
    soon = today + timedelta(days=round(weeks / 1.25 * 7))
    late = today + timedelta(days=round(weeks / 0.75 * 7))
    return Projection(
        "on_track",
        f"At your current pace you'd reach it between {soon:%b %-d} and {late:%b %-d, %Y}.",
        soon,
        late,
    )


def rate_advice(
    rate_kg_per_week: float | None, weight_kg: float, units: str = "metric"
) -> list[str]:
    """Guardrails on speed. Never suggests going faster."""
    if rate_kg_per_week is None or weight_kg <= 0:
        return []
    pct = rate_kg_per_week / weight_kg * 100
    if pct < -SAFE_LOSS_PCT:
        return [
            f"You're losing about {abs(pct):.1f}% of your bodyweight a week. Faster than about 1% "
            "a week usually costs muscle and energy: consider eating a little more. Aim for "
            "0.5 to 1% a week."
        ]
    if pct > SAFE_GAIN_PCT:
        return [
            f"You're gaining about {pct:.1f}% of your bodyweight a week. Above about 0.5% a week, "
            "most of the extra is fat: a smaller surplus works better."
        ]
    return []
