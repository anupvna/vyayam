"""The planner: turns a profile, a split and a gym into a week of workouts.

Everything here is a pure function (no database, no clock, no randomness), so the
same inputs always give the same plan, and the rules can be checked by
property-based tests across thousands of generated weeks.

The rules the planner guarantees (see `check_week`):
  1. Recovery: no muscle is trained hard on two calendar days in a row. A muscle that
     still needs rest is trained "light" (at most 2 easy sets) or not at all.
  2. Rest: at least one full rest day a week, and no more training days in a row
     than the experience level allows.
  3. Volume: each muscle's weekly sets stay at or below its upper target, and no
     single session gives one muscle more than 10 sets.
  4. Time: every session fits the time available.
  5. Safety: every exercise is doable with the gym's equipment, doesn't load an
     injured area, and isn't one the user hid.

How a week is built (`plan_week`):
  assign sessions to training days -> apply skips/swaps (re-plan the rest of the
  week) -> pick exercises for each slot -> prescribe sets/reps/effort -> balance
  weekly volume -> enforce recovery -> fit each session to the time available.
"""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from itertools import combinations, permutations
from math import ceil
from typing import Literal

from app.engine.alternatives import is_available, is_safe
from app.engine.splits import MAJOR_MUSCLES, SessionTemplate, Slot, template_from_muscles
from app.library import Exercise

# ---------------------------------------------------------------- constants

WARMUP_MINUTES = 5
WORK_SECONDS_PER_SET = 40
MAX_SETS_PER_MUSCLE_PER_SESSION = 10
LIGHT_MAX_SETS = 2
LIGHT_RIR = 4  # "reps in reserve": 4 means stop well short of failure

RIR_BY_EXPERIENCE = {"beginner": 3, "intermediate": 2, "advanced": 1}
MAX_CONSECUTIVE_DAYS = {"beginner": 4, "intermediate": 6, "advanced": 6}
DELOAD_EVERY_WEEKS = {"beginner": 6, "intermediate": 5, "advanced": 5}
PREFERRED_DIFFICULTY = {"beginner": 1, "intermediate": 2, "advanced": 2}

# Weekly hard-set targets (low, high). A set counts fully for an exercise's primary
# muscles and half for its secondary muscles.
WEEKLY_TARGETS = {
    "beginner": {"major": (6, 12), "minor": (3, 8)},
    "intermediate": {"major": (10, 16), "minor": (6, 12)},
    "advanced": {"major": (12, 20), "minor": (8, 14)},
}
# Muscles worth topping up directly when under target; the rest (forearms, lower
# back, traps...) get plenty of indirect work.
TOP_UP = frozenset(
    {
        "chest",
        "lats",
        "upper_back",
        "quads",
        "glutes",
        "hamstrings",
        "front_delts",
        "biceps",
        "triceps",
        "side_delts",
        "rear_delts",
        "calves",
        "abs",
    }
)
LIGHT_GEAR = frozenset({"resistance_bands", "suspension_trainer"})

ALL_MUSCLES = (
    "chest front_delts side_delts rear_delts lats upper_back traps biceps triceps forearms "
    "abs obliques lower_back glutes quads hamstrings adductors calves"
).split()


def target_range(muscle: str, experience: str) -> tuple[int, int]:
    group = "major" if muscle in MAJOR_MUSCLES else "minor"
    return WEEKLY_TARGETS[experience][group]


# ---------------------------------------------------------------- data shapes


@dataclass(frozen=True)
class PlanContext:
    experience: str
    goal: str
    training_days: tuple[int, ...]  # weekdays, 0 = Monday
    session_minutes: int
    equipment: frozenset[str]
    injured: frozenset[str] = frozenset()
    favorites: frozenset[str] = frozenset()
    hidden: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Override:
    """A change the user made to one day."""

    action: Literal["skip", "swap"]
    session_key: str | None = None  # swap to another session of the split...
    muscles: tuple[str, ...] = ()  # ...or to a freestyle session for these muscles


@dataclass
class PlannedExercise:
    exercise_id: str
    name: str
    kind: str
    primary: tuple[str, ...]
    secondary: tuple[str, ...]
    sets: int
    reps: tuple[int, int]
    rir: int
    rest_seconds: int
    light: bool = False

    @property
    def seconds(self) -> int:
        return self.sets * (WORK_SECONDS_PER_SET + self.rest_seconds)


@dataclass
class DayPlan:
    date: date
    status: Literal["rest", "planned", "skipped"]
    session_key: str | None = None
    session_name: str | None = None
    focus: tuple[str, ...] = ()
    exercises: list[PlannedExercise] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    swapped: bool = False
    moved: bool = False  # session changed because of a skip or swap elsewhere

    @property
    def minutes(self) -> int:
        if not self.exercises:
            return 0
        return WARMUP_MINUTES + ceil(sum(e.seconds for e in self.exercises) / 60)


@dataclass
class WeekPlan:
    start: date
    week_index: int
    deload: bool
    days: list[DayPlan]
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- small helpers


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def hard_muscles(day: DayPlan) -> frozenset[str]:
    """Muscles this day trains hard: primary muscles of any non-light exercise."""
    if day.status != "planned":
        return frozenset()
    return frozenset(m for e in day.exercises if not e.light for m in e.primary)


def estimate_minutes(exercises: list[PlannedExercise]) -> int:
    return DayPlan(date.min, "planned", exercises=exercises).minutes


def week_volume(days: list[DayPlan]) -> dict[str, float]:
    vol: dict[str, float] = defaultdict(float)
    for d in days:
        for e in d.exercises:
            for m in e.primary:
                vol[m] += e.sets
            for m in e.secondary:
                vol[m] += e.sets * 0.5
    return vol


def session_primary_sets(day: DayPlan) -> dict[str, int]:
    sets: dict[str, int] = defaultdict(int)
    for e in day.exercises:
        for m in e.primary:
            sets[m] += e.sets
    return sets


def apply_consecutive_limit(days: tuple[int, ...], experience: str) -> tuple[list[int], list[int]]:
    """Return (training days, days turned into rest). Within Mon-Sun, a run longer
    than the limit gets its extra days turned into rest days."""
    limit = MAX_CONSECUTIVE_DAYS[experience]
    kept, dropped, run = [], [], 0
    for d in range(7):
        if d in days:
            run += 1
            if run > limit:
                dropped.append(d)
                run = 0
            else:
                kept.append(d)
        else:
            run = 0
    return kept, dropped


# ---------------------------------------------------------------- prescriptions


def prescribe(kind: str, style: str | None, goal: str) -> tuple[tuple[int, int], int]:
    """(rep range, rest seconds) for an exercise."""
    if kind == "main" and (style == "power" or (goal == "strength" and style != "hypertrophy")):
        return (3, 5), 180
    if kind == "main":
        return (6, 10), 150
    return (10, 15), 90


def loading_rank(exercise: Exercise, equipment: frozenset[str]) -> int:
    """0 = can be loaded with weights/machines/cables, 1 = bands or straps,
    2 = bodyweight only. In a well-equipped gym, loadable exercises progress better."""
    usable = [set(o) for o in exercise.equipment if set(o) <= equipment]
    if any(o and not o <= LIGHT_GEAR for o in usable):
        return 0
    if any(o for o in usable):
        return 1
    return 2


def choose_exercise(
    slot: Slot, ctx: PlanContext, library: list[Exercise], used: set[str]
) -> Exercise | None:
    """Best exercise for a slot. Hard filters: equipment, injuries, hidden, not
    already in this session. Ranking: pattern order, same kind, favorites, loading
    (weights > bands > bodyweight), difficulty closest to experience, name."""
    ok = [
        e
        for e in library
        if e.id not in used
        and e.id not in ctx.hidden
        and is_available(e, ctx.equipment)
        and is_safe(e, ctx.injured)
    ]
    want = PREFERRED_DIFFICULTY[ctx.experience]

    by_pattern = [e for e in ok if e.pattern in slot.patterns]
    if by_pattern:
        return min(
            by_pattern,
            key=lambda e: (
                slot.patterns.index(e.pattern),
                e.kind != slot.kind,
                e.id not in ctx.favorites,
                loading_rank(e, ctx.equipment),
                abs(e.difficulty - want),
                e.name,
            ),
        )
    by_muscle = [e for e in ok if set(e.primary) & set(slot.muscles)]
    if by_muscle:
        return min(
            by_muscle,
            key=lambda e: (
                e.kind != slot.kind,
                -len(set(e.primary) & set(slot.muscles)),
                e.id not in ctx.favorites,
                loading_rank(e, ctx.equipment),
                abs(e.difficulty - want),
                e.name,
            ),
        )
    return None


def build_session(
    template: SessionTemplate, ctx: PlanContext, library: list[Exercise], deload: bool
) -> tuple[list[PlannedExercise], list[str]]:
    exercises: list[PlannedExercise] = []
    notes: list[str] = []
    used: set[str] = set()
    rir = RIR_BY_EXPERIENCE[ctx.experience]
    for slot in template.slots:
        ex = choose_exercise(slot, ctx, library, used)
        if ex is None:
            notes.append(
                f"No safe {slot.patterns[0].replace('_', ' ')} exercise at this gym; skipped."
            )
            continue
        used.add(ex.id)
        reps, rest = prescribe(slot.kind, template.style, ctx.goal)
        sets = slot.sets + (1 if slot.kind == "main" and ctx.experience == "advanced" else 0)
        exercises.append(
            PlannedExercise(
                exercise_id=ex.id,
                name=ex.name,
                kind=slot.kind,
                primary=ex.primary,
                secondary=ex.secondary,
                sets=max(1, ceil(sets / 2)) if deload else sets,
                reps=reps,
                rir=min(rir + 2, LIGHT_RIR) if deload else rir,
                rest_seconds=rest,
            )
        )
    return exercises, notes


# ---------------------------------------------------------------- volume, recovery, time


def _reduce_one_set(days: list[DayPlan], muscle: str, only_day: DayPlan | None = None) -> bool:
    """Remove one set that trains `muscle`, preferring accessories, bigger sets and
    later days. Returns False if nothing could be reduced."""
    candidates = []
    for di, d in enumerate(days):
        if only_day is not None and d is not only_day:
            continue
        for ei, e in enumerate(d.exercises):
            weight = 1.0 if muscle in e.primary else 0.5 if muscle in e.secondary else 0
            if weight:
                candidates.append((e.kind == "main", -weight, -e.sets, -di, -ei, di, ei))
    if not candidates:
        return False
    *_, di, ei = min(candidates)
    ex = days[di].exercises[ei]
    # Accessories never drop below 2 sets (1 set isn't worth the setup time):
    # below that they're removed. Main lifts can go down to 1 set.
    floor = 1 if ex.kind == "main" else 2
    if ex.sets > floor:
        ex.sets -= 1
    else:
        days[di].exercises.pop(ei)
    return True


def cap_session_volume(day: DayPlan) -> None:
    while True:
        over = [
            m for m, s in session_primary_sets(day).items() if s > MAX_SETS_PER_MUSCLE_PER_SESSION
        ]
        if not over or not _reduce_one_set([day], over[0], only_day=day):
            return


def balance_week_volume(days: list[DayPlan], ctx: PlanContext) -> None:
    """Trim muscles above their weekly upper target; top up muscles below their
    lower target with extra accessory sets, when a session has time and room."""
    planned = [d for d in days if d.status == "planned"]
    for _ in range(500):  # bounded loop; each pass removes one set
        vol = week_volume(planned)
        over = sorted(
            (vol[m] - target_range(m, ctx.experience)[1], m)
            for m in vol
            if vol[m] > target_range(m, ctx.experience)[1]
        )
        if not over or not _reduce_one_set(planned, over[-1][1]):
            break

    for muscle in sorted(TOP_UP):
        lo, hi = target_range(muscle, ctx.experience)
        for d in planned:
            for e in d.exercises:
                if muscle not in e.primary or e.kind != "accessory" or e.sets >= 4:
                    continue
                vol = week_volume(planned)
                if vol[muscle] >= lo or vol[muscle] + 1 > hi:
                    break
                if any(vol[m] + 1 > target_range(m, ctx.experience)[1] for m in e.primary):
                    continue
                if any(vol[m] + 0.5 > target_range(m, ctx.experience)[1] for m in e.secondary):
                    continue  # a set also counts half for secondary muscles
                session_sets = session_primary_sets(d)
                if any(session_sets[m] + 1 > MAX_SETS_PER_MUSCLE_PER_SESSION for m in e.primary):
                    continue
                e.sets += 1
                if estimate_minutes(d.exercises) > ctx.session_minutes:
                    e.sets -= 1


def enforce_recovery(days: list[DayPlan], previous_hard: frozenset[str]) -> None:
    """Walk the week in date order. Any exercise whose primary muscles were trained
    hard the day before becomes light (max 2 easy sets), so it no longer counts as
    hard. `previous_hard` is the hard muscles of the day before the week starts."""
    yesterday = previous_hard
    for d in days:
        if d.status == "planned":
            lightened = []
            for e in d.exercises:
                if set(e.primary) & yesterday and not e.light:
                    e.light = True
                    e.sets = min(e.sets, LIGHT_MAX_SETS)
                    e.rir = LIGHT_RIR
                    lightened.append(e.name)
            if lightened:
                d.notes.append(
                    "Trained yesterday, so kept light today: " + ", ".join(lightened) + "."
                )
        yesterday = hard_muscles(d)


def trim_to_minutes(exercises: list[PlannedExercise], minutes: int) -> list[PlannedExercise]:
    """Fit a session into `minutes`: keep main lifts, cut accessories from the end
    (least important last), then trim main-lift sets. Returns a new list."""
    out = [replace(e) for e in exercises]
    while out and estimate_minutes(out) > minutes:
        accessories = [i for i, e in enumerate(out) if e.kind != "main"]
        if accessories:
            i = accessories[-1]
            if out[i].sets > 2:
                out[i].sets -= 1
            else:
                out.pop(i)
            continue
        mains = [i for i, e in enumerate(out) if e.sets > 2]
        if mains:
            out[mains[-1]].sets -= 1
        elif len(out) > 1:
            out.pop()
        else:
            out[0].sets = max(1, out[0].sets - 1)
            if out[0].sets == 1:
                break
    return out


# ---------------------------------------------------------------- arranging sessions


def _template_muscles(t: SessionTemplate) -> frozenset[str]:
    return frozenset(m for s in t.slots for m in s.muscles)


def _arrange(
    open_dates: list[date],
    queue: list[SessionTemplate],
    fixed: dict[date, SessionTemplate | None],
) -> list[SessionTemplate]:
    """Choose which queued sessions go on the open days, and in what order.

    Score, best first: fewest back-to-back clashes of trained muscles; most big
    muscles covered across the week; closest to the original order. Exhaustive
    search is fine: at most 7 days and a handful of sessions.
    """
    k = len(open_dates)
    if k == 0:
        return []
    while len(queue) < k:  # more open days than sessions: repeat from the start
        queue = queue + queue[: k - len(queue)]

    fixed_muscles = {d: _template_muscles(t) if t else frozenset() for d, t in fixed.items()}
    best, best_key = None, None
    for keep in combinations(range(len(queue)), k):
        for order in permutations(keep):
            muscles = dict(fixed_muscles)
            for d, qi in zip(open_dates, order, strict=True):
                muscles[d] = _template_muscles(queue[qi])
            clashes = sum(
                len(muscles[d] & muscles.get(d - timedelta(days=1), frozenset())) for d in muscles
            )
            covered = len(frozenset().union(*muscles.values()) & MAJOR_MUSCLES)
            displacement = sum(abs(i - qi) for i, qi in enumerate(order))
            key = (clashes, -covered, displacement)
            if best_key is None or key < best_key:
                best, best_key = order, key
    return [queue[i] for i in best]  # type: ignore[union-attr]


# ---------------------------------------------------------------- the week


def plan_week(
    ctx: PlanContext,
    cycle: list[SessionTemplate],
    library: list[Exercise],
    *,
    week_start: date,
    week_index: int,
    overrides: dict[date, Override] | None = None,
    today: date | None = None,
    previous_hard: frozenset[str] = frozenset(),
    force_deload: bool = False,
) -> WeekPlan:
    overrides = overrides or {}
    week_start = monday_of(week_start)
    dates = [week_start + timedelta(days=i) for i in range(7)]
    templates = {t.key: t for t in cycle}
    notes: list[str] = []

    deload_every = DELOAD_EVERY_WEEKS[ctx.experience]
    deload = force_deload or week_index % deload_every == deload_every - 1
    if deload:
        notes.append(
            "Deload week: half the sets and easier effort, so you recover and come back stronger."
        )

    train_days, forced_rest = apply_consecutive_limit(ctx.training_days, ctx.experience)
    for wd in forced_rest:
        notes.append(
            f"{dates[wd]:%A} is a rest day: more than {MAX_CONSECUTIVE_DAYS[ctx.experience]} "
            "training days in a row slows recovery."
        )

    # 1. Base assignment: continue the cycle where last week left off.
    start = (week_index * max(1, len(train_days))) % len(cycle)
    base: dict[date, SessionTemplate] = {
        dates[wd]: cycle[(start + i) % len(cycle)] for i, wd in enumerate(train_days)
    }

    # 2. Skips and swaps.
    session: dict[date, SessionTemplate | None] = dict(base)
    skipped: list[date] = []
    swapped: set[date] = set()
    queue_extra: list[SessionTemplate] = []
    remove_from_queue: list[str] = []
    for d in sorted(overrides):
        if d not in base:
            continue  # rest days stay rest days: no skipping or swapping them
        o = overrides[d]
        original = session.get(d)
        if o.action == "skip":
            skipped.append(d)
            session[d] = None
            if original:
                queue_extra.append(original)
        else:
            chosen = (
                templates.get(o.session_key or "")
                if o.session_key
                else template_from_muscles("freestyle", "Your pick", list(o.muscles))
            )
            if chosen is None:
                continue
            session[d] = chosen
            swapped.add(d)
            if original and original.key != chosen.key:
                queue_extra.append(original)
                if o.session_key:
                    remove_from_queue.append(chosen.key)

    if skipped or swapped:
        anchor = max(skipped + list(swapped))
        if today is not None:
            anchor = max(anchor, today - timedelta(days=1))
        open_dates = [
            d for d in sorted(base) if d > anchor and d not in skipped and d not in swapped
        ]
        # (template, displaced?) pairs: displaced sessions came from skipped/swapped days.
        entries = [(base[d], False) for d in open_dates] + [(t, True) for t in queue_extra]
        # A session already trained via a swap doesn't need doing again this week,
        # wherever it sits (a later day, or displaced by a skip). Prefer removing a
        # displaced copy, so the regular schedule stays put.
        for key in remove_from_queue:
            matches = [i for i, (t, _) in enumerate(entries) if t.key == key]
            if matches:
                entries.pop(max(matches, key=lambda i: (entries[i][1], i)))
        queue = [t for t, _ in entries]
        owed = [t for t, displaced in entries if displaced]
        fixed = {d: session.get(d) for d in dates if d not in open_dates}
        arranged = _arrange(open_dates, queue, fixed)
        for d, t in zip(open_dates, arranged, strict=True):
            session[d] = t
        placed = {t.key for t in arranged}
        dropped = [t.name for t in owed if t.key not in placed]
        for t in owed:
            if t.key in placed:
                notes.append(f"{t.name} moved later in the week.")
        if dropped:
            notes.append(
                "Not enough days left for "
                + ", ".join(dropped)
                + " without cramming two sessions into one day. Muscles that fall short "
                "this week get extra sets in your other sessions, where time and recovery allow."
            )

    # 3. Build each day.
    days: list[DayPlan] = []
    for d in dates:
        t = session.get(d)
        if d in skipped:
            days.append(DayPlan(d, "skipped", notes=["Skipped."]))
        elif t is None:
            days.append(DayPlan(d, "rest"))
        else:
            exercises, day_notes = build_session(t, ctx, library, deload)
            day = DayPlan(
                d,
                "planned",
                session_key=t.key,
                session_name=t.name,
                focus=t.focus,
                exercises=exercises,
                notes=day_notes,
                swapped=d in swapped,
                moved=d in base and base[d].key != t.key and d not in swapped,
            )
            cap_session_volume(day)
            days.append(day)

    # 4. Volume, recovery, time.
    balance_week_volume(days, ctx)
    enforce_recovery(days, previous_hard)
    for day in days:
        if day.status == "planned":
            day.exercises = trim_to_minutes(day.exercises, ctx.session_minutes)

    return WeekPlan(week_start, week_index, deload, days, notes)


# ---------------------------------------------------------------- checking


def check_week(
    week: WeekPlan,
    ctx: PlanContext,
    library: dict[str, Exercise],
    previous_hard: frozenset[str] = frozenset(),
) -> list[str]:
    """Every rule the planner promises. Returns the violations (empty = valid).
    Used by the tests, and later to validate the AI coach's suggested changes."""
    problems: list[str] = []
    yesterday = previous_hard
    run = longest = 0
    for d in week.days:
        hard = hard_muscles(d)
        clash = hard & yesterday
        if clash:
            problems.append(f"{d.date}: {sorted(clash)} trained hard two days in a row")
        yesterday = hard
        run = run + 1 if d.status == "planned" else 0
        longest = max(longest, run)
        if d.status != "planned":
            continue
        if d.minutes > ctx.session_minutes:
            problems.append(f"{d.date}: {d.minutes} min exceeds {ctx.session_minutes}")
        for m, s in session_primary_sets(d).items():
            if s > MAX_SETS_PER_MUSCLE_PER_SESSION:
                problems.append(f"{d.date}: {s} sets for {m} in one session")
        for e in d.exercises:
            ex = library[e.exercise_id]
            if not is_available(ex, ctx.equipment):
                problems.append(f"{d.date}: {e.exercise_id} needs equipment you don't have")
            if not is_safe(ex, ctx.injured):
                problems.append(f"{d.date}: {e.exercise_id} loads an injured area")
            if e.exercise_id in ctx.hidden:
                problems.append(f"{d.date}: {e.exercise_id} is hidden")
            if e.light and (e.sets > LIGHT_MAX_SETS or e.rir < LIGHT_RIR):
                problems.append(f"{d.date}: {e.exercise_id} marked light but isn't")
    if all(d.status == "planned" for d in week.days):
        problems.append("no rest day this week")
    if longest > MAX_CONSECUTIVE_DAYS[ctx.experience]:
        problems.append(f"{longest} training days in a row")
    vol = week_volume(week.days)
    for m, v in vol.items():
        hi = target_range(m, ctx.experience)[1]
        if v > hi:
            problems.append(f"{m}: {v} weekly sets exceeds {hi}")
    return problems
