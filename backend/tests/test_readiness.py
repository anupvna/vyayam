"""Readiness and the safety layer. The red-flag rule is tested exhaustively: every
combination of inputs with any red flag must stop training."""

from hypothesis import given
from hypothesis import strategies as st

from app.catalog import BODY_PART_IDS
from app.engine.readiness import (
    RED_FLAGS,
    SORE_AREAS,
    STOP_MESSAGE,
    CheckIn,
    assess,
    readiness_score,
)

scale = st.integers(1, 5)
sore = st.frozensets(st.sampled_from(sorted(SORE_AREAS)))
pain = st.frozensets(st.sampled_from(sorted(BODY_PART_IDS)))
flags = st.frozensets(st.sampled_from(sorted(RED_FLAGS)), min_size=1)


@given(sleep=scale, energy=scale, stress=scale, sore=sore, pain=pain, red=flags)
def test_any_red_flag_always_stops_training(sleep, energy, stress, sore, pain, red) -> None:
    a = assess(CheckIn(sleep, energy, stress, sore, pain, red))
    assert a.verdict == "stop"
    assert a.messages == (STOP_MESSAGE,)
    assert "emergency" in STOP_MESSAGE and "doctor" in STOP_MESSAGE


@given(sleep=scale, energy=scale, stress=scale, sore=sore, pain=pain)
def test_without_red_flags_never_stops(sleep, energy, stress, sore, pain) -> None:
    a = assess(CheckIn(sleep, energy, stress, sore, pain))
    assert a.verdict in ("rest", "lighter", "normal")
    assert 0 <= a.score <= 100
    assert a.avoid_areas == pain  # painful areas are always kept out of today's plan


@given(sleep=scale, energy=scale, stress=scale)
def test_better_inputs_never_lower_the_score(sleep, energy, stress) -> None:
    base = readiness_score(CheckIn(sleep, energy, stress))
    if sleep < 5:
        assert readiness_score(CheckIn(sleep + 1, energy, stress)) >= base
    if stress > 1:
        assert readiness_score(CheckIn(sleep, energy, stress - 1)) >= base


def test_verdict_bands() -> None:
    assert assess(CheckIn(5, 5, 1)).verdict == "normal"
    assert assess(CheckIn(3, 3, 3)).verdict == "lighter"
    assert assess(CheckIn(1, 1, 5)).verdict == "rest"


def test_pain_gets_professional_advice_and_persistence_escalates() -> None:
    a = assess(CheckIn(5, 5, 1, pain_areas=frozenset({"knee"})))
    assert "physiotherapist" in a.messages[0]
    b = assess(CheckIn(5, 5, 1, pain_areas=frozenset({"knee"})), {"knee": 3})
    assert b.persistent_pain == ("knee",)
    assert any("checked by a qualified professional" in m for m in b.messages)


def test_soreness_marks_muscles_light() -> None:
    a = assess(CheckIn(5, 5, 1, sore_areas=frozenset({"legs"})))
    assert {"quads", "hamstrings"} <= a.sore_muscles
