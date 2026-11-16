# Progress: body, training and photos

The Progress tab has three parts. All the maths lives in the backend engine
(`app/engine/body.py`) and the stats API (`app/api/stats.py`), with tests.

## Body

**Trend weight.** Daily weight swings 1 to 2 kg with water, salt and food. The app
shows a smoothed trend (an exponential moving average, α = 0.1 per day; gaps between
weigh-ins are weighted as if those days passed). The trend is what counts.

**Rate.** The slope of the trend over the last 3 weeks, needing at least 4 weigh-ins
across 7+ days. Advice appears if you lose more than 1% of body weight a week (muscle
loss risk) or gain more than 0.5% a week (mostly fat).

**Goal date.** Remaining distance ÷ current rate, shown as a range: from 125% of your
current pace (earliest) to 75% (latest). Pace changes, so a single date would be false
precision. Other states: reached, holding steady, moving the wrong way, not enough data.

**Body fat.** A scale, DEXA or other reading if you enter one; otherwise the US Navy tape
estimate from neck, waist (and hips for women) and height. Every method is an estimate:
compare like with like over time.

**BMI** is shown with a note: it can't tell muscle from fat.

Logging a weigh-in for the latest day also updates the weight on your profile, which
the planner and calorie maths use.

## Training

- **This week**: sessions done vs planned, sets so far and last week's total, new
  records, and big muscles that were under target last week.
- **Recovery map**: per muscle, from logged working sets and soreness in today's check-in.
  3+ hard sets today or yesterday, or sore = needs rest; 3+ two days ago = recovering;
  otherwise fresh.
- **Sets per muscle** this week against the target range for your goal and experience.
  A secondary muscle counts half a set.
- **Push vs pull** set counts, with a note if one side is more than 25% ahead.
- **Strength**: estimated 1-rep max (Epley, sets of 12 reps or fewer) per session, with
  records marked.
- **Consistency**: 12 weeks of trained, missed, skipped, rest and planned days. Days
  before you joined count as rest. Uses your current training days.

## Photos

Progress photos are stored only in the browser on your phone (IndexedDB). They are
never uploaded, so they're not in any server backup. The app asks the browser to keep
them stored persistently, and "Save a copy" downloads any photo.

- Reminder every 14 days, with a pose guide and tips for consistent photos.
- Photos are resized to at most 1600 px and saved as JPEG to save space.
- Compare two dates per pose, side by side or with a slider.

## Charts

Apache ECharts, loaded only when the Progress tab opens (so the first screen stays
fast). Every chart has a text label for screen readers and a table view where the
numbers matter.
