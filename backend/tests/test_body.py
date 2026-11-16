from datetime import date, timedelta
from math import log10

from hypothesis import given
from hypothesis import strategies as st

from app.engine.body import (
    navy_body_fat,
    project,
    rate_advice,
    recent_rate,
    slope_per_week,
    trend_weights,
)

D = date(2026, 11, 16)


# ---------------------------------------------------------------- Navy body fat


def _navy_inches_male(height, neck, waist) -> float:
    """The original imperial Navy formula, used as an independent cross-check."""
    i = 1 / 2.54
    return 86.010 * log10((waist - neck) * i) - 70.041 * log10(height * i) + 36.76


def test_navy_male_worked_example() -> None:
    # 180 cm, neck 40 cm, waist 90 cm -> about 18.4%
    assert navy_body_fat("male", 180, 40, 90) == 18.4
    assert abs(navy_body_fat("male", 180, 40, 90) - _navy_inches_male(180, 40, 90)) < 0.5


def _navy_inches_female(height, neck, waist, hips) -> float:
    i = 1 / 2.54
    return 163.205 * log10((waist + hips - neck) * i) - 97.684 * log10(height * i) - 78.387


def test_navy_female_worked_example() -> None:
    # 165 cm, neck 33 cm, waist 72 cm, hips 98 cm -> about 26.9% (imperial form: 27.2%)
    assert navy_body_fat("female", 165, 33, 72, 98) == 26.9
    assert (
        abs(navy_body_fat("female", 165, 33, 72, 98) - _navy_inches_female(165, 33, 72, 98)) < 0.5
    )


def test_navy_rejects_impossible_measurements() -> None:
    assert navy_body_fat("male", 180, 45, 40) is None  # waist smaller than neck
    assert navy_body_fat("female", 165, 33, 72) is None  # women need hips


@given(height=st.floats(150, 210), neck=st.floats(30, 48), extra=st.floats(25, 70))
def test_navy_bigger_waist_means_more_fat(height, neck, extra) -> None:
    a = navy_body_fat("male", height, neck, neck + extra)
    b = navy_body_fat("male", height, neck, neck + extra + 3)
    if a is not None and b is not None:
        assert b >= a


# ---------------------------------------------------------------- trend


def test_trend_smooths_a_spike() -> None:
    points = [(D + timedelta(days=i), 80.0) for i in range(10)] + [(D + timedelta(days=10), 82.0)]
    trend = trend_weights(points)
    assert trend[-1][2] == 80.2  # a 2 kg water spike moves the trend only 0.2 kg


def test_trend_scales_with_gaps() -> None:
    one_day = trend_weights([(D, 80.0), (D + timedelta(days=1), 81.0)])[-1][2]
    week_gap = trend_weights([(D, 80.0), (D + timedelta(days=7), 81.0)])[-1][2]
    assert 80 < one_day < week_gap < 81


@given(st.lists(st.floats(40, 200), min_size=1, max_size=60))
def test_trend_stays_within_the_range_of_weigh_ins(weights) -> None:
    trend = trend_weights([(D + timedelta(days=i), w) for i, w in enumerate(weights)])
    for _, _, t in trend:
        assert min(weights) - 1e-9 <= t <= max(weights) + 1e-9


# ---------------------------------------------------------------- rate and projection


def test_rate_from_steady_loss() -> None:
    # losing 0.1 kg a day = 0.7 kg a week
    pts = [(D + timedelta(days=i), 90 - 0.1 * i) for i in range(21)]
    assert round(slope_per_week(pts), 2) == -0.7


def test_rate_needs_enough_data() -> None:
    assert slope_per_week([(D, 80.0), (D + timedelta(days=1), 79.9)]) is None
    few = [(D + timedelta(days=i), 80.0) for i in range(5)]
    assert slope_per_week(few) is None  # only 4 days apart


def test_recent_rate_uses_the_trend() -> None:
    pts = [(D + timedelta(days=i), 90 - 0.1 * i) for i in range(30)]
    rate = recent_rate(trend_weights(pts), D + timedelta(days=29))
    # The true rate is -0.7 kg/week; the smoothed trend lags a little behind it.
    assert -0.75 < rate < -0.55


def test_projection_gives_a_date_range() -> None:
    p = project(80, 75, -0.5, D)  # 10 weeks at this pace
    assert p.status == "on_track"
    assert p.earliest == D + timedelta(days=56)  # 8 weeks at 125% pace
    assert p.latest == D + timedelta(days=93)  # about 13.3 weeks at 75% pace
    assert p.earliest < p.latest


def test_projection_edge_cases() -> None:
    assert project(80, 80.2, -0.5, D).status == "reached"
    assert project(80, 75, None, D).status == "not_enough_data"
    assert project(80, 75, 0.01, D).status == "flat"
    assert project(80, 75, 0.4, D).status == "wrong_way"  # gaining while wanting to lose


@given(current=st.floats(40, 200), target=st.floats(40, 200), rate=st.floats(-2, 2))
def test_projection_range_is_always_ordered_and_in_the_future(current, target, rate) -> None:
    p = project(current, target, rate, D)
    if p.status == "on_track":
        assert D <= p.earliest <= p.latest


def test_rate_guardrails() -> None:
    assert rate_advice(-1.2, 80)  # 1.5% a week: too fast
    assert "0.5 to 1%" in rate_advice(-1.2, 80)[0]
    assert rate_advice(-0.6, 80) == []  # 0.75% a week: fine
    assert rate_advice(0.6, 80)  # gaining 0.75% a week: mostly fat
    assert rate_advice(None, 80) == []
