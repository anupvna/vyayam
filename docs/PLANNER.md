# How the planner works

The planner is the deterministic engine at the core of Vyayam. It lives in
`backend/app/engine/` as pure functions: no database, no clock, no randomness. The
same inputs always produce the same week, which is what makes it testable and what
lets it act as the safety check for the AI coach later.

## Inputs

- **Profile**: experience, goal, training days, session length, injured areas
- **Active gym**: the equipment available
- **Preferences**: favorite and hidden exercises
- **Split**: a cycle of sessions (built-in or custom)
- **Day overrides**: skips and swaps for this week
- **Previous day**: what was trained hard the day before the week starts

## Splits and slots

A session template is a list of **slots**, not exercises. A slot says "a horizontal
push, main lift, 3 sets". For each slot the planner picks the best exercise the user
can actually do:

1. Hard filters: has the equipment, doesn't load an injured area, not hidden, not
   already in this session.
2. Ranking: preferred movement pattern, same kind (main lift vs accessory),
   favorites, loading quality (weights > bands > bodyweight), difficulty closest to
   the user's experience, then name (so it's deterministic).

So one split works in a commercial gym, a home gym or a hotel room. Sessions rotate
through the split's cycle across weeks: a 3-day week on a 4-session split continues
where last week stopped.

Built-in splits: full body, upper/lower, push/pull/legs, upper/lower + PPL, PHUL,
body-part ("bro") split, chest+triceps / back+biceps / legs+shoulders, Arnold, and
torso/limbs. Users can also build a custom split by choosing muscles per session.

## Prescriptions

| | Reps | Rest | Effort |
|---|---|---|---|
| Main lift, strength goal or power day | 3 to 5 | 3 min | |
| Main lift otherwise | 6 to 10 | 2.5 min | Reps in reserve (RIR): beginner 3, intermediate 2, advanced 1 |
| Accessory | 10 to 15 | 1.5 min | |

**Deload**: every 6th week for beginners and every 5th for others. Sets are halved
and effort is eased. A fatigue-triggered deload (`force_deload`) is wired in for the
readiness check-in in Step 4.

## Weekly volume

Weekly hard sets per muscle are counted as 1 per set for primary muscles and 0.5 for
secondary muscles. Targets by experience (sets per week):

| | Big muscles | Small muscles |
|---|---|---|
| Beginner | 6 to 12 | 3 to 8 |
| Intermediate | 10 to 16 | 6 to 12 |
| Advanced | 12 to 20 | 8 to 14 |

The planner trims any muscle above its upper target, then tops up muscles below
their lower target with extra accessory sets when a session has time. No single
session gives one muscle more than 10 sets.

## Recovery and rest

- **No muscle is trained hard two calendar days in a row.** If it would be (for
  example back-to-back full-body days, or a swap that repeats yesterday's muscles),
  those exercises are made *light*: at most 2 sets, 4 reps in reserve.
- **At least one full rest day** a week (the profile allows at most 6 days).
- **Consecutive training days** are capped at 4 for beginners and 6 for everyone
  else. Extra days in a row become rest days, with a note explaining why.

## Skips and swaps

- **Skip a day**: its session joins a queue with the sessions still to come. The
  planner chooses which sessions go on the remaining training days, and in what
  order, by searching every arrangement and scoring: fewest back-to-back muscle
  clashes, then most big muscles covered this week, then closest to the original
  order. It never adds a session on a rest day and never puts two sessions on one
  day. If there are more sessions than days, the least useful one is dropped and the
  user is told.
- **Swap today**: do another session from the split, or pick muscles for a
  freestyle session. The session you were meant to do moves later in the week, and
  any later copy of the one you chose is removed.

## Time-boxed sessions

"I have 35 minutes": accessories are cut from the end (least important last), first
down to 2 sets and then removed. Main lifts are kept, and only lose sets if there's
still no time. Session time is estimated as a 5-minute warm-up plus, per set,
40 seconds of work and the prescribed rest.

## How it's tested

`check_week()` encodes every rule above and returns any violations. Property-based
tests (Hypothesis) generate random people, gyms, injuries, favorites, hidden lists,
built-in and custom splits, skips, swaps and freestyle sessions, and assert that
`check_week()` returns nothing.

- **Every test run (CI):** 3,600 generated weeks: 3,000 in the main rule check
  (`test_no_generated_week_ever_breaks_a_rule`), plus 300 each for determinism and
  for skips never pushing volume past targets.
- **Thorough run, recorded:** 25,000 generated weeks in the main rule check, **0
  failing**, in 2 minutes 36 seconds (Hypothesis also discarded 2,564 invalid draws
  before running them; they aren't counted). Reproduce it with:

  ```bash
  cd backend
  PLANNER_EXAMPLES=25000 pytest tests/test_planner.py -k no_generated_week --hypothesis-show-statistics
  ```

Along the way these tests found and fixed three real bugs:

1. A swap on a rest day created a workout on that rest day.
2. Top-up sets could push one muscle past the per-session cap.
3. Top-up sets ignored the half-set they add to *secondary* muscles, pushing a
   muscle past its weekly target.
