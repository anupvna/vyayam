# Logging, progression, readiness and safety

## Safety layer (runs first, can't be overridden)

| Check-in input | What happens |
|---|---|
| Any red flag: chest pain or pressure, dizziness or fainting, unusual shortness of breath, sharp joint pain, numbness or tingling | **No workout.** "Stop" screen: call emergency services for chest pain, fainting or trouble breathing; otherwise see a doctor before training again. |
| Pain in a body area | Exercises that load that area are removed for today. Advice to rest it and see a doctor or physiotherapist if it lasts or worsens. |
| Pain in the same area on 3+ check-ins within 14 days | Stronger message: get it checked by a qualified professional before training it again. |

Rules are in `backend/app/engine/readiness.py`. A property test checks every
combination of inputs: any red flag always stops training, and no red flag never
does.

## Readiness

Score from 0 to 100: sleep 35%, energy 35%, stress 20%, soreness 10%.

| Score | Verdict | Effect on today |
|---|---|---|
| 60+ | Normal | As planned |
| 35 to 59 | Lighter | One set fewer per exercise, one more rep in reserve |
| Below 35 | Rest suggested | "Rest today" or "Do the easy version" (every exercise light) |

Sore areas keep the matching muscles light today. If 3 or more check-ins in the
last 10 days average below 45, the current week becomes a deload.

## Double progression

1. Keep the weight and add reps until every set reaches the top of the rep range.
2. Then add weight and go back to the bottom of the range.
3. Miss the bottom of the range two sessions in a row at the same weight, and the
   weight drops about 10%.

| Increments | Metric | Imperial |
|---|---|---|
| Barbell / machine, lower body | +5 kg | +10 lb |
| Barbell / machine, upper body | +2.5 kg | +5 lb |
| Dumbbells and kettlebells | +2 kg | +5 lb |
| Bodyweight and bands | add reps, then a harder variation | |

Weights are rounded to loadable plates (2.5 kg or 5 lb steps). They're stored in
kg at full precision, so 135 lb always comes back as 135 lb. Light days use about
80% of the working weight; deload weeks about 90%.

## On the workout screen

- **Last time, set by set.** Each exercise shows the previous session ("Nov 21: 40 × 16,
  45 × 16, 50 × 14 lb").
- **A different weight on each set is fine.** If last time was a pyramid and the target
  keeps the weight, set 1 starts from last time's set 1, set 2 from set 2, and so on.
  Progression follows the heaviest sets.
- **Choose today's sets.** A − / + control changes the number of sets for today, from
  what's already logged (at least 1) up to 6, or the plan's number if that's higher.
  Past about 6 hard sets of one exercise in a session, more sets add fatigue more than
  growth, so the app suggests training it on another day instead. The choice is kept
  on the device for that day.
- **Clear weight labels.** Dumbbell weights are per dumbbell ("30 kg each"). Barbell
  weights include the bar, so 0 isn't accepted there (a standard bar is 20 kg / 45 lb).
  For bodyweight exercises the box is for added weight; leave it blank for bodyweight.
- Reps in reserve isn't asked after each set any more (testers found it confusing). The
  plan still says how hard to push ("stop 2 reps before failure").

## e1RM and PRs

Estimated one-rep max uses the Epley formula: `weight × (1 + reps / 30)`, used only
for sets of 1 to 12 reps, where it's reasonably accurate. A set is a PR when its e1RM
beats every earlier set of that exercise. The very first set isn't a PR.

## Logging and duplicate-proof sync

Every set gets a UUID generated on the phone before it's sent. The server inserts
with `ON CONFLICT (id) DO NOTHING`, so retrying the same set (bad gym Wi-Fi, a double
tap, an offline queue replaying) never creates a duplicate. A set id that belongs to
another user is refused with 409, without revealing anything about that set. This is
the foundation for the offline sync in Step 8.
