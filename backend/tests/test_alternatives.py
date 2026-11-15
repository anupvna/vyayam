"""Alternatives ranking: examples plus property-based tests.

The properties are the safety contract: for ANY gym, ANY injuries and ANY
hidden/favorite choices, an alternative is never something you can't do, never
something that loads an injured area, never hidden, never the same exercise.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.catalog import BODY_PART_IDS, EQUIPMENT_IDS
from app.engine.alternatives import find_alternatives, is_available, is_safe
from app.library import load_library

LIB = load_library()
EXERCISES = list(LIB.values())
ALL = frozenset(EQUIPMENT_IDS)


def ids(xs) -> list[str]:
    return [x.id for x in xs]


# --- examples -----------------------------------------------------------------


def test_heavy_lifts_swap_for_heavy_lifts() -> None:
    assert ids(find_alternatives(LIB["deadlift"], EXERCISES, equipment=ALL))[:2] == [
        "romanian_deadlift",
        "trap_bar_deadlift",
    ]
    assert ids(find_alternatives(LIB["back_squat"], EXERCISES, equipment=ALL)) == [
        "leg_press",
        "smith_squat",
        "hack_squat",
    ]


def test_machine_taken_at_a_home_gym() -> None:
    home = frozenset({"dumbbells", "adjustable_bench", "pull_up_bar", "resistance_bands"})
    alts = ids(find_alternatives(LIB["lat_pulldown"], EXERCISES, equipment=home))
    assert alts and all(a in {"pull_up", "chin_up", "assisted_pull_up"} for a in alts)


def test_injury_removes_exercises_that_load_the_area() -> None:
    alts = find_alternatives(
        LIB["back_squat"], EXERCISES, equipment=ALL, injured=frozenset({"knee"})
    )
    assert alts and all("knee" not in a.loads for a in alts)


def test_favorite_moves_up_among_equally_good_matches() -> None:
    # Barbell and cable curls are equally good swaps for a dumbbell curl;
    # a favorite breaks the tie. (Favorites never outrank a better match.)
    plain = ids(find_alternatives(LIB["dumbbell_curl"], EXERCISES, equipment=ALL))
    fav = ids(
        find_alternatives(
            LIB["dumbbell_curl"], EXERCISES, equipment=ALL, favorites=frozenset({"cable_curl"})
        )
    )
    assert plain[:2] == ["barbell_curl", "cable_curl"]
    assert fav[:2] == ["cable_curl", "barbell_curl"]


def test_hidden_exercises_never_suggested() -> None:
    alts = ids(
        find_alternatives(
            LIB["back_squat"], EXERCISES, equipment=ALL, hidden=frozenset({"leg_press"})
        )
    )
    assert "leg_press" not in alts


def test_no_equipment_means_bodyweight_only() -> None:
    for a in find_alternatives(LIB["bench_press"], EXERCISES, equipment=frozenset()):
        assert () in a.equipment


# --- properties -----------------------------------------------------------------

equipment_sets = st.frozensets(st.sampled_from(sorted(EQUIPMENT_IDS)))
injury_sets = st.frozensets(st.sampled_from(sorted(BODY_PART_IDS)), max_size=4)
exercise_id_sets = st.frozensets(st.sampled_from(sorted(LIB)), max_size=10)


@settings(max_examples=500)
@given(
    target=st.sampled_from(EXERCISES),
    equipment=equipment_sets,
    injured=injury_sets,
    hidden=exercise_id_sets,
    favorites=exercise_id_sets,
)
def test_alternatives_never_break_the_rules(target, equipment, injured, hidden, favorites):
    alts = find_alternatives(
        target, EXERCISES, equipment=equipment, injured=injured, hidden=hidden, favorites=favorites
    )
    assert len(alts) <= 3
    assert len(set(ids(alts))) == len(alts)  # no duplicates
    for a in alts:
        assert a.id != target.id
        assert a.id not in hidden
        assert is_available(a, equipment)  # you can actually do it
        assert is_safe(a, injured)  # it doesn't load an injured area
        assert a.pattern == target.pattern or set(a.primary) & set(target.primary)


@settings(max_examples=300)
@given(target=st.sampled_from(EXERCISES), equipment=equipment_sets, injured=injury_sets)
def test_same_pattern_always_ranks_first_when_one_exists(target, equipment, injured):
    alts = find_alternatives(target, EXERCISES, equipment=equipment, injured=injured)
    patterns = [a.pattern == target.pattern for a in alts]
    # Once a different-pattern exercise appears, no same-pattern one follows it.
    assert patterns == sorted(patterns, reverse=True)


@settings(max_examples=200)
@given(target=st.sampled_from(EXERCISES), equipment=equipment_sets)
def test_more_equipment_never_means_fewer_alternatives(target, equipment):
    fewer = find_alternatives(target, EXERCISES, equipment=equipment)
    more = find_alternatives(target, EXERCISES, equipment=equipment | {"dumbbells", "barbell"})
    assert len(more) >= len(fewer)


@given(target=st.sampled_from(EXERCISES), equipment=equipment_sets)
def test_deterministic(target, equipment):
    first = find_alternatives(target, EXERCISES, equipment=equipment)
    reversed_library = find_alternatives(target, list(reversed(EXERCISES)), equipment=equipment)
    assert ids(first) == ids(reversed_library)  # library order doesn't matter
