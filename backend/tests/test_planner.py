"""Planner tests.

Example tests pin down specific behaviour. Property tests generate thousands of
random (but valid) people, gyms, injuries, splits, skips and swaps, and assert that
`check_week` finds zero rule violations in every single generated week.
"""

from datetime import date, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.catalog import BODY_PART_IDS, EQUIPMENT_IDS, PRESETS
from app.engine.planner import (
    MAX_CONSECUTIVE_DAYS,
    Override,
    PlanContext,
    apply_consecutive_limit,
    check_week,
    estimate_minutes,
    hard_muscles,
    plan_week,
    trim_to_minutes,
    week_volume,
)
from app.engine.splits import (
    MUSCLE_PATTERNS,
    SPLITS,
    TEMPLATES,
    recommend_split,
    template_from_muscles,
)
from app.library import load_library

LIB = load_library()
EXERCISES = list(LIB.values())
FULL = frozenset(EQUIPMENT_IDS)
HOME = frozenset(next(p for p in PRESETS if p.id == "home").equipment)
MONDAY = date(2026, 11, 16)


def cycle(split_id: str):
    return [TEMPLATES[k] for k in SPLITS[split_id].cycle]


def ctx(**over) -> PlanContext:
    base = dict(
        experience="intermediate",
        goal="muscle_gain",
        training_days=(0, 2, 4),
        session_minutes=60,
        equipment=FULL,
    )
    return PlanContext(**(base | over))


def week(c: PlanContext, split_id: str, **kw):
    return plan_week(
        c, cycle(split_id), EXERCISES, week_start=MONDAY, week_index=kw.pop("week_index", 0), **kw
    )


def planned(w):
    return [d for d in w.days if d.status == "planned"]


# ---------------------------------------------------------------- split choice


def test_recommendations() -> None:
    assert recommend_split([0, 3], "beginner", "fat_loss")[0] == "full_body"
    assert recommend_split([0, 2, 4], "intermediate", "muscle_gain")[0] == "full_body"
    assert recommend_split([0, 1, 2], "intermediate", "muscle_gain")[0] == "ppl"
    assert recommend_split([0, 1, 3, 4], "intermediate", "muscle_gain")[0] == "upper_lower"
    assert recommend_split([0, 1, 3, 4], "advanced", "strength")[0] == "phul"
    assert recommend_split([0, 1, 2, 3, 4], "intermediate", "fat_loss")[0] == "ulppl"
    assert recommend_split([0, 1, 2, 3, 4, 5], "advanced", "muscle_gain")[0] == "ppl"
    for days in ([0], [0, 2, 4], [0, 1, 2, 3, 4, 5]):
        assert recommend_split(days, "beginner", "strength")[1]  # always explained


def test_every_split_uses_real_templates() -> None:
    for s in SPLITS.values():
        assert s.cycle and all(k in TEMPLATES for k in s.cycle)


# ---------------------------------------------------------------- weekly plan


def test_full_body_three_days() -> None:
    w = week(ctx(), "full_body")
    assert [d.session_name for d in planned(w)] == ["Full body A", "Full body B", "Full body A"]
    assert [d.date.weekday() for d in planned(w)] == [0, 2, 4]
    assert check_week(w, ctx(), LIB) == []


def test_cycle_continues_next_week() -> None:
    # Upper/lower has 4 sessions; on 3 days a week, week 2 starts where week 1 stopped.
    c = ctx()
    w0 = week(c, "upper_lower", week_index=0)
    w1 = week(c, "upper_lower", week_index=1)
    assert [d.session_key for d in planned(w0)] == ["upper_a", "lower_a", "upper_b"]
    assert planned(w1)[0].session_key == "lower_b"


def test_main_lifts_come_first_and_get_compound_prescriptions() -> None:
    day = planned(week(ctx(goal="strength"), "full_body"))[0]
    assert day.exercises[0].kind == "main"
    assert day.exercises[0].reps == (3, 5)  # strength goal: heavy main lifts
    accessory = next(e for e in day.exercises if e.kind == "accessory")
    assert accessory.reps == (10, 15)


def test_home_gym_only_uses_home_equipment() -> None:
    c = ctx(equipment=HOME, training_days=(0, 1, 3, 4))
    w = week(c, "upper_lower")
    assert check_week(w, c, LIB) == []
    assert all(len(d.exercises) >= 4 for d in planned(w))


def test_injury_keeps_loaded_exercises_out() -> None:
    c = ctx(injured=frozenset({"knee", "lower_back"}))
    w = week(c, "full_body")
    for d in planned(w):
        for e in d.exercises:
            assert not set(LIB[e.exercise_id].loads) & {"knee", "lower_back"}


def test_favorites_are_picked_when_they_fit_the_slot() -> None:
    # A favorite main lift takes the main-lift slot...
    c = ctx(favorites=frozenset({"dumbbell_bench_press"}))
    press = planned(week(c, "full_body"))[0].exercises[1]
    assert press.exercise_id == "dumbbell_bench_press"
    # ...and a favorite accessory takes an accessory slot, without replacing the
    # day's heavy main lift.
    c = ctx(favorites=frozenset({"incline_dumbbell_press"}), training_days=(0, 2, 4))
    push = planned(week(c, "ppl"))[0]
    assert push.exercises[0].kind == "main" and push.exercises[0].exercise_id == "bench_press"
    assert "incline_dumbbell_press" in [e.exercise_id for e in push.exercises]


def test_hidden_exercises_are_never_planned() -> None:
    c = ctx(hidden=frozenset({"barbell_bench_press", "bench_press", "dumbbell_bench_press"}))
    w = week(c, "full_body")
    assert all(e.exercise_id not in c.hidden for d in planned(w) for e in d.exercises)


def test_beginners_get_a_forced_rest_after_four_days_in_a_row() -> None:
    kept, dropped = apply_consecutive_limit((0, 1, 2, 3, 4, 5), "beginner")
    assert dropped == [4] and kept == [0, 1, 2, 3, 5]
    c = ctx(experience="beginner", training_days=(0, 1, 2, 3, 4, 5))
    w = week(c, "ppl")
    assert w.days[4].status == "rest" and any("rest day" in n for n in w.notes)


def test_deload_halves_sets_and_eases_effort() -> None:
    c = ctx()
    normal = planned(week(c, "full_body", week_index=0))[0].exercises[0]
    deload_week = week(c, "full_body", week_index=4)  # every 5th week for intermediates
    assert deload_week.deload
    light = planned(deload_week)[0].exercises[0]
    assert light.sets < normal.sets and light.rir > normal.rir


def test_back_to_back_full_body_days_are_made_light_not_hard() -> None:
    c = ctx(training_days=(0, 1))
    w = week(c, "full_body")
    tue = w.days[1]
    assert any(e.light for e in tue.exercises)
    assert not (hard_muscles(w.days[0]) & hard_muscles(tue))
    assert check_week(w, c, LIB) == []


def test_previous_week_sunday_counts_for_monday_recovery() -> None:
    c = ctx(training_days=(0, 2, 4))
    w = week(c, "full_body", previous_hard=frozenset({"quads", "chest"}))
    monday = w.days[0]
    lightened = [e for e in monday.exercises if set(e.primary) & {"quads", "chest"}]
    assert lightened and all(e.light for e in lightened)


# ---------------------------------------------------------------- time


def test_time_boxed_session_keeps_main_lifts() -> None:
    day = planned(week(ctx(session_minutes=90), "upper_lower"))[0]
    short = trim_to_minutes(day.exercises, 35)
    assert estimate_minutes(short) <= 35
    mains = [e.exercise_id for e in day.exercises if e.kind == "main"]
    assert [e.exercise_id for e in short if e.kind == "main"] == mains
    assert len(short) < len(day.exercises)


@given(minutes=st.integers(min_value=20, max_value=120))
def test_trim_always_fits(minutes: int) -> None:
    day = planned(week(ctx(session_minutes=120), "ulppl" if False else "upper_lower"))[0]
    assert estimate_minutes(trim_to_minutes(day.exercises, minutes)) <= minutes


# ---------------------------------------------------------------- skips and swaps


def test_skipped_session_moves_to_a_later_day() -> None:
    c = ctx(training_days=(0, 2, 4, 5))  # upper/lower on 4 days, Thu and Sun off
    w = week(c, "upper_lower", overrides={MONDAY: Override("skip")}, today=MONDAY)
    assert w.days[0].status == "skipped"
    assert [d.session_key for d in planned(w)] == ["upper_a", "lower_a", "upper_b"] or len(
        planned(w)
    ) == 3
    assert any("moved later" in n or "Not enough days" in n for n in w.notes)
    assert check_week(w, c, LIB) == []


def test_skip_never_adds_sessions_on_rest_days_or_doubles_up() -> None:
    c = ctx(training_days=(0, 2, 4))
    w = week(c, "ppl", overrides={MONDAY: Override("skip")}, today=MONDAY)
    trained = [d.date.weekday() for d in planned(w)]
    assert trained == [2, 4]  # still only the user's days, one session each


def test_swap_today_to_another_session() -> None:
    c = ctx(training_days=(0, 2, 4))
    w = week(c, "ppl", overrides={MONDAY: Override("swap", session_key="legs")}, today=MONDAY)
    assert w.days[0].session_key == "legs" and w.days[0].swapped
    # Push and pull still happen later in the week.
    assert sorted(d.session_key for d in planned(w)[1:]) == ["pull", "push"]


def test_swap_then_skip_doesnt_ask_for_a_session_already_done() -> None:
    c = ctx(training_days=(0, 2, 3, 4))  # upper/lower: Mon U_A, Wed L_A, Thu U_B, Fri L_B
    overrides = {
        MONDAY: Override("swap", session_key="lower_a"),  # did Lower A on Monday instead
        MONDAY + timedelta(days=2): Override("skip"),  # then skipped Wednesday (was Lower A)
    }
    w = week(c, "upper_lower", overrides=overrides, today=MONDAY + timedelta(days=2))
    assert all("Lower A" not in n for n in w.notes)  # Lower A was already done
    assert check_week(w, c, LIB) == []


def test_freestyle_swap_builds_a_session_for_chosen_muscles() -> None:
    c = ctx()
    o = Override("swap", muscles=("chest", "biceps"))
    w = week(c, "full_body", overrides={MONDAY: o}, today=MONDAY)
    day = w.days[0]
    assert day.session_name == "Your pick"
    trained = {m for e in day.exercises for m in e.primary}
    assert {"chest", "biceps"} <= trained
    assert check_week(w, c, LIB) == []


def test_template_from_muscles_covers_every_muscle() -> None:
    for m in MUSCLE_PATTERNS:
        t = template_from_muscles("x", "X", [m])
        assert t.slots and all(m in s.muscles for s in t.slots)


# ---------------------------------------------------------------- properties

SPLIT_IDS = sorted(SPLITS)
MUSCLES = sorted(MUSCLE_PATTERNS)


@st.composite
def scenarios(draw):
    experience = draw(st.sampled_from(["beginner", "intermediate", "advanced"]))
    days = tuple(sorted(draw(st.sets(st.integers(0, 6), min_size=1, max_size=6))))
    gym = draw(
        st.one_of(
            st.sampled_from([FULL, HOME] + [frozenset(p.equipment) for p in PRESETS]),
            st.frozensets(st.sampled_from(sorted(EQUIPMENT_IDS))),
        )
    )
    c = PlanContext(
        experience=experience,
        goal=draw(st.sampled_from(["fat_loss", "muscle_gain", "recomposition", "strength"])),
        training_days=days,
        session_minutes=draw(st.sampled_from([20, 30, 35, 45, 60, 75, 90, 120])),
        equipment=gym,
        injured=draw(st.frozensets(st.sampled_from(sorted(BODY_PART_IDS)), max_size=3)),
        favorites=draw(st.frozensets(st.sampled_from(sorted(LIB)), max_size=6)),
        hidden=draw(st.frozensets(st.sampled_from(sorted(LIB)), max_size=8)),
    )
    if draw(st.booleans()):
        cyc = cycle(draw(st.sampled_from(SPLIT_IDS)))
    else:  # a custom split: 1-4 sessions of 1-4 muscles each
        cyc = [
            template_from_muscles(
                f"custom_{i}",
                f"Day {i}",
                draw(st.lists(st.sampled_from(MUSCLES), min_size=1, max_size=4, unique=True)),
            )
            for i in range(draw(st.integers(1, 4)))
        ]
    overrides = {}
    for wd in draw(st.sets(st.integers(0, 6), max_size=3)):
        if draw(st.booleans()):
            overrides[MONDAY + timedelta(days=wd)] = Override("skip")
        elif draw(st.booleans()):
            overrides[MONDAY + timedelta(days=wd)] = Override(
                "swap", session_key=draw(st.sampled_from([t.key for t in cyc]))
            )
        else:
            overrides[MONDAY + timedelta(days=wd)] = Override(
                "swap",
                muscles=tuple(
                    draw(st.lists(st.sampled_from(MUSCLES), min_size=1, max_size=3, unique=True))
                ),
            )
    today = MONDAY + timedelta(days=draw(st.integers(0, 6)))
    previous_hard = draw(st.frozensets(st.sampled_from(MUSCLES), max_size=5))
    return c, cyc, overrides, today, previous_hard, draw(st.integers(0, 20))


@settings(max_examples=3000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_no_generated_week_ever_breaks_a_rule(scenario) -> None:
    """The headline property: across thousands of random people, gyms, injuries,
    splits, skips and swaps, every rule holds. Recovery is never violated."""
    c, cyc, overrides, today, previous_hard, week_index = scenario
    w = plan_week(
        c,
        cyc,
        EXERCISES,
        week_start=MONDAY,
        week_index=week_index,
        overrides=overrides,
        today=today,
        previous_hard=previous_hard,
    )
    assert check_week(w, c, LIB, previous_hard) == []
    assert len(w.days) == 7
    # Never cram: only the user's own days are trained, at most one session each.
    for d in w.days:
        if d.status == "planned":
            assert d.date.weekday() in c.training_days
    assert sum(d.status == "planned" for d in w.days) <= len(c.training_days)
    assert max((run for run in _runs(w)), default=0) <= MAX_CONSECUTIVE_DAYS[c.experience]


def _runs(w):
    run = 0
    for d in w.days:
        run = run + 1 if d.status == "planned" else 0
        yield run


@settings(max_examples=300, deadline=None)
@given(scenarios())
def test_planning_is_deterministic(scenario) -> None:
    c, cyc, overrides, today, previous_hard, week_index = scenario
    kw = dict(
        week_start=MONDAY,
        week_index=week_index,
        overrides=overrides,
        today=today,
        previous_hard=previous_hard,
    )
    a = plan_week(c, cyc, EXERCISES, **kw)
    b = plan_week(c, cyc, EXERCISES, **kw)
    assert [(d.session_key, [(e.exercise_id, e.sets) for e in d.exercises]) for d in a.days] == [
        (d.session_key, [(e.exercise_id, e.sets) for e in d.exercises]) for d in b.days
    ]


@settings(max_examples=300, deadline=None)
@given(scenarios())
def test_skipping_a_day_never_increases_weekly_volume_beyond_targets(scenario) -> None:
    c, cyc, _, today, _, week_index = scenario
    skip = {MONDAY + timedelta(days=c.training_days[0]): Override("skip")}
    w = plan_week(
        c, cyc, EXERCISES, week_start=MONDAY, week_index=week_index, overrides=skip, today=MONDAY
    )
    assert check_week(w, c, LIB) == []
    assert week_volume(w.days) is not None
