# Cardio, mat work and training anywhere

Everything here is optional. Lifting plans never depend on cardio; a short warm-up is
advised before lifting.

## On Today

- **Training at**: pick where you train today: your usual gym, another of your gyms, or
  **Home, mat only**. Only that day changes. Each exercise that can't be done there is
  swapped for the closest one that can (same ranking as the library's alternatives); a
  loaded lift becoming bodyweight gets 12 to 20 reps instead. If nothing fits (pulling
  with only a mat), it's left out with a note. Code: `engine/places.py`.
- **Warm-up (advised)**: 5 easy minutes on a machine your gym has (treadmill, bike,
  elliptical, rower, stair climber, jump rope), or marching and jumping jacks on a mat.
  One tap logs it.
- **Finisher (optional)**: 8 to 10 minutes of intervals, for fat loss and recomposition
  goals or when cardio is set to "lots". Jump rope or bodyweight HIIT when there are no
  machines.
- **Cool-down (optional)**: up to 6 stretches matched to the muscles trained, with
  holds and how-to. Code: `engine/cooldown.py`.
- **Activity**: log anything, any day, including rest days and gym-free days.

## Logging

Pick the activity; only the fields that make sense appear:

| Activity | Fields |
|---|---|
| Treadmill | minutes, speed, incline, distance |
| Stair climber, elliptical | minutes, level, effort |
| Exercise bike, rowing machine | minutes, level, distance, effort |
| Walk, run | minutes, speed, distance |
| Cycling outside, swim | minutes, distance, effort |
| Jump rope, stretching / yoga, sport | minutes, effort |
| Mat workout, bodyweight HIIT | minutes, effort, and the moves you did (tap to pick) |

Mat moves come from the library's bodyweight exercises (core, legs, upper body), plus
HIIT moves and the cool-down stretches. Calories are optional: enter the machine's
number, or the app saves an estimate (shown as "≈").

Entries carry an id made on the phone, so they sync safely after being logged offline.

## Calorie estimates

- Treadmill, walk and run with a speed: the ACSM metabolic equations (walking below
  8 km/h, running above), including incline.
- Everything else: MET values per effort level, from the ranges in the Compendium of
  Physical Activities.
- kcal = MET x 3.5 x body weight (kg) / 200 per minute, using your latest weigh-in.

Estimates are often off by about 20%, which is why they're marked.

## Weekly cardio

Set in Profile: **Auto** (follows the goal), none (0), light (75), regular (150) or lots
(225 minutes a week). Auto is regular for fat loss and light for the other goals.
Stretching, cool-downs and mat (floor strength) workouts are logged but don't count as
cardio minutes; HIIT and jump rope do. Progress → Training shows the week day by day.

## Equipment and exercises added

- Equipment: exercise mat, jump rope, stair climber (original illustrations), and a
  "Home: mat only" gym preset.
- 15 floor exercises with original coaching content: crunch, reverse crunch, bicycle
  crunch, lying leg raise, hollow hold, bird dog, mountain climber, superman, flutter
  kicks, Russian twist, single-leg glute bridge, wall sit, jump squat, incline push-up,
  prone T raise.
- 15 stretches, written for Vyayam.

## The coach

The coach sees the cardio target, what's logged this week, today's warm-up, finisher and
stretches, and where you're training. It can propose **Train at home on a mat today**
(and back to the gym), checked by the engine like every other action.
