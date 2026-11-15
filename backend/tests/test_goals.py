"""Goal guardrails: example tests plus property-based tests (Hypothesis).

Property tests generate hundreds of random-but-valid inputs and check rules that
must hold for every one of them, not just the examples we thought of.
"""

from hypothesis import given
from hypothesis import strategies as st

from app.engine.goals import assess_goal, bmi, format_weight, safe_timeline_weeks

weights = st.floats(min_value=30, max_value=300, allow_nan=False)
heights = st.floats(min_value=120, max_value=230, allow_nan=False)
sexes = st.sampled_from(["male", "female"])
goals = st.sampled_from(["fat_loss", "muscle_gain", "recomposition", "strength"])


def codes(advice) -> set[str]:
    return {a.code for a in advice}


# --- examples ---------------------------------------------------------------


def test_bmi() -> None:
    assert round(bmi(70, 175), 1) == 22.9


def test_timeline_for_losing_10kg_from_80() -> None:
    # 1%/week of 80 kg = 0.8 kg -> 13 weeks; 0.5%/week = 0.4 kg -> 25 weeks
    assert safe_timeline_weeks(80, 70) == (13, 25)


def test_timeline_for_gaining_5kg_from_70() -> None:
    # 0.5%/week = 0.35 kg -> 15 weeks; 0.25%/week = 0.175 kg -> 29 weeks
    assert safe_timeline_weeks(70, 75) == (15, 29)


def test_no_timeline_when_target_is_current_weight() -> None:
    assert safe_timeline_weeks(70, 70.3) is None


def test_warns_on_dangerously_low_body_fat() -> None:
    male = assess_goal(
        sex="male", height_cm=178, weight_kg=80, goal="fat_loss", target_body_fat_pct=6
    )
    female = assess_goal(
        sex="female", height_cm=165, weight_kg=62, goal="fat_loss", target_body_fat_pct=12
    )
    assert "body_fat_too_low" in codes(male)
    assert "body_fat_too_low" in codes(female)


def test_reasonable_body_fat_target_is_fine() -> None:
    advice = assess_goal(
        sex="male", height_cm=178, weight_kg=80, goal="fat_loss", target_body_fat_pct=12
    )
    assert advice == []


def test_warns_on_underweight_target() -> None:
    advice = assess_goal(
        sex="male", height_cm=180, weight_kg=75, goal="fat_loss", target_weight_kg=55
    )
    assert "target_underweight" in codes(advice)
    warning = next(a for a in advice if a.code == "target_underweight")
    assert "60 kg" in warning.message  # 18.5 * 1.8^2 = 59.9 -> suggest 60


def test_advice_uses_the_users_units() -> None:
    advice = assess_goal(
        sex="male",
        height_cm=180,
        weight_kg=79.83,
        goal="fat_loss",
        target_weight_kg=55,
        units="imperial",
    )
    messages = " ".join(a.message for a in advice)
    assert "lb" in messages and " kg" not in messages
    assert "at least 133 lb" in messages  # 59.94 kg = 132.1 lb, rounded up to 133


def test_format_weight() -> None:
    assert format_weight(72.5, "metric") == "72.5 kg"
    assert format_weight(72.57478, "imperial") == "160 lb"


def test_flags_goal_pointing_the_wrong_way() -> None:
    gain_down = assess_goal(
        sex="male", height_cm=178, weight_kg=80, goal="muscle_gain", target_weight_kg=75
    )
    lose_up = assess_goal(
        sex="male", height_cm=178, weight_kg=80, goal="fat_loss", target_weight_kg=85
    )
    assert "goal_direction" in codes(gain_down)
    assert "goal_direction" in codes(lose_up)


# --- properties ---------------------------------------------------------------


@given(current=weights, target=weights)
def test_timeline_pace_is_always_within_safe_rates(current: float, target: float) -> None:
    weeks = safe_timeline_weeks(current, target)
    if weeks is None:
        assert abs(target - current) < 0.5
        return
    fastest, slowest = weeks
    assert 1 <= fastest <= slowest
    weekly_change_pct = abs(target - current) / fastest / current * 100
    max_pct = 1.0 if target < current else 0.5
    # The fastest suggested pace never exceeds the safe maximum.
    assert weekly_change_pct <= max_pct + 1e-9


@given(
    sex=sexes,
    height=heights,
    weight=weights,
    goal=goals,
    target_w=st.none() | weights,
    target_bf=st.none() | st.floats(min_value=3, max_value=50, allow_nan=False),
)
def test_assessment_never_crashes_and_warns_exactly_when_unsafe(
    sex, height, weight, goal, target_w, target_bf
) -> None:
    advice = assess_goal(
        sex=sex,
        height_cm=height,
        weight_kg=weight,
        goal=goal,
        target_weight_kg=target_w,
        target_body_fat_pct=target_bf,
    )
    floor = 8.0 if sex == "male" else 15.0
    assert ("body_fat_too_low" in codes(advice)) == (target_bf is not None and target_bf < floor)
    assert ("target_underweight" in codes(advice)) == (
        target_w is not None and bmi(target_w, height) < 18.5
    )
    for a in advice:
        assert a.level in ("info", "warning") and a.message
