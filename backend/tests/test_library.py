"""The exercise library is data, so it gets tested like code."""

import pytest

from app.catalog import EQUIPMENT_IDS, PATTERN_IDS, PRESETS
from app.engine.alternatives import find_alternatives, is_available
from app.library import Exercise, load_library

LIB = load_library()
ALL_EQUIPMENT = frozenset(EQUIPMENT_IDS)


def test_library_loads_and_ids_are_snake_case() -> None:
    assert len(LIB) >= 70
    for exercise_id in LIB:
        assert exercise_id == exercise_id.lower() and " " not in exercise_id


def test_every_pattern_has_exercises() -> None:
    assert {e.pattern for e in LIB.values()} == PATTERN_IDS


def test_every_exercise_has_full_coaching_content() -> None:
    for e in LIB.values():
        assert e.setup and e.execution and e.mistakes, e.id
        assert e.breathing.strip() and e.safety.strip(), e.id


def test_names_are_unique() -> None:
    names = [e.name for e in LIB.values()]
    assert len(names) == len(set(names))


def test_every_main_lift_trains_at_least_one_major_muscle() -> None:
    major = {"chest", "lats", "upper_back", "quads", "glutes", "hamstrings", "front_delts"}
    for e in LIB.values():
        if e.kind == "main":
            assert set(e.primary) & major, e.id


@pytest.mark.parametrize("exercise", list(LIB.values()), ids=lambda e: e.id)
def test_full_gym_offers_at_least_two_alternatives(exercise: Exercise) -> None:
    # The spec: every exercise shows 2-3 alternatives (in a gym that has everything).
    assert len(find_alternatives(exercise, LIB.values(), equipment=ALL_EQUIPMENT)) >= 2


@pytest.mark.parametrize(
    "preset", [p for p in PRESETS if p.id in ("home", "garage")], ids=lambda p: p.id
)
def test_smaller_gyms_still_offer_an_alternative_for_everything(preset) -> None:
    equipment = frozenset(preset.equipment)
    for e in LIB.values():
        if is_available(e, equipment):
            assert find_alternatives(e, LIB.values(), equipment=equipment), (preset.id, e.id)


def test_bad_data_is_rejected() -> None:
    good = LIB["back_squat"].model_dump()
    for change in (
        {"pattern": "twerk"},
        {"primary": ["spleen"]},
        {"equipment": [["jetpack"]]},
        {"loads": ["soul"]},
        {"secondary": ["quads"]},  # quads is already primary
    ):
        with pytest.raises(ValueError):
            Exercise.model_validate(good | change)
