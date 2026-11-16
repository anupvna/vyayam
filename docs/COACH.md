# The AI coach

The coach explains your training and adapts it on request. It never decides the plan:
the tested engine does. The AI's job is the conversation.

## What it can do

- **Explain** today's targets, deloads, sets per muscle, reps in reserve, and progress,
  all from your own data.
- **Adapt**, by proposing changes you confirm with a tap: skip today, swap today's
  session, shorten today to 30 or 45 minutes, undo today's change, train at home on a
  mat today (or back to the gym), stop suggesting an exercise, or favorite one. Goal,
  days, gyms and injuries stay in Profile.
- **Cardio**: this week's minutes against the target, what's logged (with calories),
  today's warm-up, finisher and stretches.
- **Answer basics** on recovery, sleep and nutrition (protein, creatine).

"Ask the coach why" under every target on Today opens the coach with that question.

## How a message is handled

```
message ─▶ safety screen ─▶ your data (context) ─▶ Groq ─▶ checks ─▶ reply
                │                                   │ fails
                │                                   ▼
                │                                 Gemini ─▶ checks
                │                                   │ fails
                ▼                                   ▼
         fixed safe answer               rule-based coach (no AI)
```

1. **Safety screen** (`app/coach/safety.py`). Medical red flags (chest pain, fainting,
   trouble breathing, a pop or swelling, numbness), crisis, disordered eating,
   steroids and weight-loss drugs, diagnosis questions and health conditions get a
   fixed, careful answer. These messages are **never sent to an AI**.
2. **Context** (`app/coach/context.py`). Your plan, targets and their reasons, check-in,
   sets per muscle, recovery, strength and body trend, in your units.
3. **Providers** (`app/coach/providers.py`). Groq first (`openai/gpt-oss-120b`, with a
   strict JSON schema), then Gemini (`gemini-flash-latest`). Each must reply in JSON:
   the text plus any proposed actions.
4. **Checks** (`app/coach/service.py`). A reply is accepted only if it:
   - is valid JSON in the reply schema,
   - passes the safety check (no drug dosing, starvation calories, multi-day fasts,
     "train through pain"),
   - **invents no numbers**: every number with kg, lb, % or kcal must already be in
     your data or your message (`grounding.py`),
   - is short enough.

   A failing reply gets one retry with the reason; then the next provider answers.
5. **Actions** (`app/coach/actions.py`). Every proposal is checked by the engine:
   rest days can't be skipped, a swap must be a session in your split, hiding an
   exercise needs an alternative at your gym, and so on. Invalid ones are dropped,
   never shown. They're checked **again** when you tap Apply, and applied through the
   same endpoint code as the rest of the app.
6. **Rule-based coach** (`engine_reply.py`). If no provider is set up or all fail, the
   coach still answers the common questions and proposes the same checked actions.

## Privacy

- Sent to the AI: training numbers and settings (age, sex, height, goal, plan,
  targets, logged sets, body trend). **Not sent**: email, name, password, birth date,
  or progress photos (those never leave your phone).
- Safety-screened messages aren't sent to any AI.
- The conversation is stored so the coach remembers the last few turns. Clear it any
  time with Clear on the Coach screen.
- Free tiers: Google's Gemini API terms allow free-tier content to be used to improve
  Google products. Gemini is only the backup, and receives no identity, but if you'd
  rather not, leave `GEMINI_API_KEY` empty.

## Configuration (`.env`)

| Setting | Default | |
|---|---|---|
| `GROQ_API_KEY` | empty | Main provider. Free at console.groq.com |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Any Groq chat model; GPT-OSS models get strict JSON |
| `GEMINI_API_KEY` | empty | Backup. Free at aistudio.google.com |
| `GEMINI_MODEL` | `gemini-flash-latest` | An alias; Google emails 2 weeks before it moves |
| `COACH_TIMEOUT_SECONDS` | 20 | Per provider call |
| `COACH_MESSAGES_PER_10_MIN` | 20 | Per user, to stay inside free tiers |
| `COACH_MESSAGES_PER_DAY` | 100 | Per user |

With no keys, the coach runs on the rule-based coach alone.

## Evaluation

44 scenarios (`app/coach/scenarios.json`) in seven groups: explaining, adapting the
plan, cardio, progress, nutrition basics, safety and robustness (prompt injection, off-topic,
prompt leaks, gibberish). Each runs against a realistic user (a lifter with two weeks
of logs, a beginner cutting too fast, a rest day, a skipped day, an imperial user) and
checks the safety category, the checked actions, and what the reply mentions.

```bash
cd backend
python -m app.coach.eval --provider engine     # rule-based coach: 44/44, also in CI
python -m app.coach.eval --provider groq -v    # needs GROQ_API_KEY; -v shows replies
python -m app.coach.eval --provider gemini
python -m app.coach.eval                       # the real chain: Groq, then Gemini
```

The evaluation uses the test database and wipes it first. Free tiers limit tokens per
minute (Groq: 8K a minute for GPT-OSS, and one coach message uses about 3 to 4K), so AI
runs pause 8 seconds between scenarios and wait whenever the provider says "rate
limited" (`--pause` to change). A full Groq run takes about 15 minutes.

In everyday use one person rarely sends two messages within a few seconds; when a burst
does hit the limit, Gemini answers instead, then the rule-based coach.
