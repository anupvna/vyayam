"""Cardio engine, cool-down stretches and training somewhere else for a day."""

from datetime import date

import pytest

from app.engine.cardio import (
    ACTIVITIES,
    estimate_calories,
    finisher,
    met_for,
    met_from_speed,
    rest_day,
    warmup,
    weekly_target,
)
from app.engine.cooldown import STRETCHES, cooldown, minutes
from app.engine.places import MAT, substitute_day
from app.engine.planner import DayPlan, PlannedExercise
from app.library import load_library

LIB = load_library()


# ---------------------------------------------------------------- calories (ACSM, worked by hand)


def test_walking_equation() -> None:
    # 5 km/h = 83.3 m/min: VO2 = 0.1*83.3 + 3.5 = 11.83 ml/kg/min = 3.38 MET
    assert met_from_speed(5.0) == pytest.approx(3.381, abs=0.01)
    # 70 kg, 30 min: 3.38 * 3.5 * 70 / 200 * 30 = 124 kcal
    assert estimate_calories(met_from_speed(5.0), 30, 70) == 124


def test_incline_adds_a_lot_when_walking() -> None:
    # + 1.8 * 83.3 * 0.05 = 7.5 ml/kg/min -> 19.33 / 3.5 = 5.52 MET
    assert met_from_speed(5.0, 5) == pytest.approx(5.524, abs=0.01)


def test_running_equation() -> None:
    # 10 km/h = 166.7 m/min: VO2 = 0.2*166.7 + 3.5 = 36.83 -> 10.52 MET; 70 kg 30 min = 387
    assert met_from_speed(10.0) == pytest.approx(10.52, abs=0.01)
    assert estimate_calories(met_from_speed(10.0), 30, 70) == 387


def test_machines_use_met_by_intensity() -> None:
    assert met_for("bike", intensity="easy") < met_for("bike") < met_for("bike", intensity="hard")
    assert met_for("treadmill", speed_kmh=5, incline_pct=5) == pytest.approx(5.524, abs=0.01)
    assert met_for("walk") == pytest.approx(met_from_speed(5.0))  # default walking pace


def test_every_activity_has_a_calorie_path() -> None:
    for a in ACTIVITIES:
        assert met_for(a.id) > 1


# ---------------------------------------------------------------- targets and suggestions


def test_goal_decides_and_the_person_can_override() -> None:
    assert weekly_target("fat_loss", None) == 150
    assert weekly_target("muscle_gain", None) == 75
    assert weekly_target("muscle_gain", "lots") == 225
    assert weekly_target("fat_loss", "none") == 0


def test_warmup_uses_what_the_gym_has() -> None:
    assert warmup(frozenset({"treadmill", "bike"})).activity == "treadmill"
    assert warmup(frozenset({"rower"})).activity == "rower"
    assert warmup(MAT).activity == "hiit"  # marching and jumping jacks
    assert warmup(MAT).minutes == 5


def test_finisher_only_when_it_helps() -> None:
    assert finisher("muscle_gain", "light", frozenset({"bike"})) is None
    assert finisher("fat_loss", "none", frozenset({"bike"})) is None
    assert finisher("fat_loss", "regular", frozenset({"bike"})).activity == "bike"
    assert finisher("fat_loss", "regular", frozenset({"jump_rope"})).activity == "jump_rope"
    assert finisher("fat_loss", "regular", MAT).activity == "hiit"
    assert finisher("strength", "lots", frozenset({"rower"})).activity == "rower"


def test_rest_day_suggestion_tracks_the_week() -> None:
    assert "20 of 150" in rest_day("regular", 20, 150)
    assert "already" in rest_day("regular", 160, 150)
    assert rest_day("none", 0, 0) is None


# ---------------------------------------------------------------- cool-down


def test_cooldown_matches_the_muscles_trained() -> None:
    picked = cooldown(["chest", "triceps", "front_delts"])
    names = [s.name for s in picked]
    assert names == ["Doorway chest stretch", "Overhead triceps stretch"]  # no repeats
    assert 1 <= minutes(picked) <= 3


def test_every_muscle_has_a_stretch() -> None:
    from app.catalog import MUSCLES

    covered = {m for s in STRETCHES for m in s.muscles}
    assert {m.id for m in MUSCLES} <= covered


# ---------------------------------------------------------------- training somewhere else


def _pe(ex_id: str, reps=(6, 10)) -> PlannedExercise:
    e = LIB[ex_id]
    return PlannedExercise(e.id, e.name, e.kind, e.primary, e.secondary, 3, reps, 2, 120)


def test_mat_day_swaps_each_exercise_for_a_floor_version() -> None:
    day = DayPlan(
        date(2026, 11, 16),
        "planned",
        exercises=[
            _pe("back_squat"),
            _pe("bench_press"),
            _pe("plank", (30, 60)),
            _pe("lat_pulldown"),
        ],
    )
    out = substitute_day(day, LIB, equipment=MAT, place_name="home (mat only)")
    ids = [e.exercise_id for e in out.exercises]
    assert all(not LIB[i].equipment[0] or () in LIB[i].equipment for i in ids)  # all bodyweight
    assert ids[0] in ("bodyweight_squat", "jump_squat", "wall_sit")
    assert ids[1] in ("push_up", "decline_push_up", "incline_push_up")
    assert ids[2] == "plank"  # already works on a mat: kept as is
    assert out.exercises[0].reps == (12, 20)  # more reps without the load
    assert out.exercises[2].reps == (30, 60)
    assert "Lat pulldown" in " ".join(out.notes)  # nothing on a mat replaces pulling
    assert len(out.exercises) == 3
    assert out.minutes < day.minutes


def test_rest_days_are_left_alone() -> None:
    rest = DayPlan(date(2026, 11, 18), "rest")
    assert substitute_day(rest, LIB, equipment=MAT, place_name="x") is rest


def test_no_exercise_is_used_twice() -> None:
    day = DayPlan(date(2026, 11, 16), "planned", exercises=[_pe("back_squat"), _pe("front_squat")])
    out = substitute_day(day, LIB, equipment=MAT, place_name="home")
    ids = [e.exercise_id for e in out.exercises]
    assert len(ids) == len(set(ids))
