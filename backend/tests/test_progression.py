from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.catalog import EQUIPMENT_IDS
from app.engine.progression import (
    KG_PER_LB,
    LoggedSet,
    Session,
    e1rm,
    is_pr,
    load_type,
    next_target,
    round_weight,
)
from app.library import load_library

LIB = load_library()
D = date(2026, 11, 16)


def session(weight: float, *reps: int, days_ago: int = 0) -> Session:
    return Session(D - timedelta(days=days_ago), tuple(LoggedSet(weight, r) for r in reps))


# ---------------------------------------------------------------- e1RM and PRs


def test_epley() -> None:
    assert e1rm(100, 1) == 100
    assert round(e1rm(100, 5), 2) == 116.67
    assert round(e1rm(60, 10), 1) == 80.0
    assert e1rm(100, 13) is None  # not reliable above 12 reps
    assert e1rm(0, 5) is None and e1rm(50, 0) is None


def test_pr_detection() -> None:
    previous = [LoggedSet(100, 5), LoggedSet(100, 4)]
    assert is_pr(LoggedSet(100, 6), previous)
    assert is_pr(LoggedSet(105, 5), previous)
    assert not is_pr(LoggedSet(100, 5), previous)  # ties aren't records
    assert not is_pr(LoggedSet(80, 5), previous)
    assert not is_pr(LoggedSet(100, 5), [])  # the very first set isn't a PR
    assert not is_pr(LoggedSet(0, 20), previous)


@given(w=st.floats(1, 500), r=st.integers(1, 11))
def test_e1rm_grows_with_reps_and_weight(w: float, r: int) -> None:
    assert e1rm(w, r + 1) > e1rm(w, r) >= w
    assert e1rm(w + 1, r) > e1rm(w, r)


# ---------------------------------------------------------------- load types and rounding


def test_load_types_follow_the_users_gear() -> None:
    full = frozenset(EQUIPMENT_IDS)
    assert load_type(LIB["back_squat"], full) == "barbell_lower"
    assert load_type(LIB["bench_press"], full) == "barbell_upper"
    assert load_type(LIB["romanian_deadlift"], frozenset({"dumbbells"})) == "dumbbell"
    assert load_type(LIB["leg_press"], full) == "machine_lower"
    assert load_type(LIB["lat_pulldown"], full) == "machine_upper"
    assert load_type(LIB["push_up"], full) is None
    assert load_type(LIB["band_pull_apart"], full) is None


def test_rounding_to_loadable_weights() -> None:
    assert round_weight(61.3, "metric", "barbell_upper") == 62.5
    assert round_weight(61.3, "metric", "barbell_upper", down=True) == 60.0
    # 135 lb is a real plate load; stored in kg, shown as exactly 135 lb.
    kg = round_weight(61.0, "imperial", "barbell_upper")
    assert round(kg / KG_PER_LB, 6) == 135.0


# ---------------------------------------------------------------- double progression


def test_first_time_has_no_weight() -> None:
    t = next_target([], (6, 10), "barbell_upper", "metric", rir=2)
    assert t.change == "first" and t.weight_kg is None and t.reps == 6


def test_hit_top_of_range_adds_weight() -> None:
    t = next_target([session(60, 10, 10, 10)], (6, 10), "barbell_upper", "metric", rir=2)
    assert t.change == "increase" and t.weight_kg == 62.5 and t.reps == 6


def test_lower_body_jumps_more() -> None:
    t = next_target([session(100, 10, 10, 10)], (6, 10), "barbell_lower", "metric", rir=2)
    assert t.weight_kg == 105


def test_imperial_increments() -> None:
    w = 135 * KG_PER_LB
    t = next_target([session(w, 10, 10, 10)], (6, 10), "barbell_upper", "imperial", rir=2)
    assert round(t.weight_kg / KG_PER_LB) == 140


def test_in_range_adds_a_rep_at_same_weight() -> None:
    t = next_target([session(60, 8, 7, 7)], (6, 10), "barbell_upper", "metric", rir=2)
    assert t.change == "more_reps" and t.weight_kg == 60 and t.reps == 8


def test_one_miss_holds_two_misses_reduce() -> None:
    one = [session(60, 5, 4, 4)]
    assert next_target(one, (6, 10), "barbell_upper", "metric", rir=2).change == "hold"
    two = [session(60, 5, 4, 4), session(60, 5, 5, 4, days_ago=3)]
    t = next_target(two, (6, 10), "barbell_upper", "metric", rir=2)
    assert t.change == "reduce" and t.weight_kg == 52.5  # 54 kg rounded down to 52.5


def test_bodyweight_progresses_reps() -> None:
    t = next_target([session(0, 12, 11, 10)], (10, 15), None, "metric", rir=2)
    assert t.weight_kg is None and t.reps == 11


def test_light_and_deload_days_are_lighter() -> None:
    hist = [session(100, 8, 8, 8)]
    normal = next_target(hist, (6, 10), "barbell_upper", "metric", rir=2)
    light = next_target(hist, (6, 10), "barbell_upper", "metric", rir=2, light=True)
    deload = next_target(hist, (6, 10), "barbell_upper", "metric", rir=2, deload=True)
    assert light.weight_kg < deload.weight_kg < normal.weight_kg


reps = st.integers(0, 20)
weights = st.sampled_from([20.0, 40.0, 60.0, 62.5, 100.0, 140.0])


@given(
    hist=st.lists(
        st.tuples(weights, st.lists(reps, min_size=1, max_size=5)), min_size=1, max_size=5
    ),
    lo=st.integers(3, 10),
    width=st.integers(0, 6),
    units=st.sampled_from(["metric", "imperial"]),
    kind=st.sampled_from(["barbell_lower", "barbell_upper", "dumbbell", "machine_upper"]),
)
def test_progression_rules_always_hold(hist, lo, width, units, kind) -> None:
    hi = lo + width
    history = [session(w, *r, days_ago=i * 3) for i, (w, r) in enumerate(hist)]
    t = next_target(history, (lo, hi), kind, units, rir=2)
    last_weight = max(s.weight_kg for s in history[0].sets)
    assert t.weight_kg is not None and t.weight_kg >= 0
    assert lo <= t.reps <= hi
    if t.weight_kg > last_weight + 1e-6:  # weight only goes up after hitting the top
        assert t.change == "increase"
        assert all(s.reps >= hi for s in history[0].sets if s.weight_kg == last_weight)
        assert t.weight_kg - last_weight <= 10 * KG_PER_LB + 2.5  # never a big jump
    if t.weight_kg < last_weight - 1e-6:  # and only drops after repeated misses
        assert t.change == "reduce"


@pytest.mark.parametrize("exercise_id", sorted(LIB))
def test_every_exercise_gets_a_sensible_target(exercise_id: str) -> None:
    kind = load_type(LIB[exercise_id], frozenset(EQUIPMENT_IDS))
    w = 0.0 if kind is None else 50.0
    t = next_target([session(w, 10, 10)], (8, 12), kind, "metric", rir=2)
    assert t.reason
