# Vyayam

A personal gym coach that runs as an installable web app (PWA). A deterministic,
tested engine decides training plans, progression, recovery and body calculations.
An AI coach explains and adapts, and every change it proposes is checked by the
engine's rules before it is shown.

> Training aid, not medical advice.

## Run locally

Requirements: Docker, Python 3.12, Node 22+.

```bash
cp .env.example .env                 # local settings (never committed)
docker compose up -d                 # Postgres on localhost:5433
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"

cd backend
python -m app.migrate                # create tables
uvicorn app.main:app --reload        # API on http://localhost:8000
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                          # app on http://localhost:5173 (proxies /api to :8000)
```

Production-style (one service): `npm run build` in `frontend/`, then FastAPI serves the
app and the API together on http://localhost:8000.

## Tests

```bash
cd backend && pytest                 # API, auth, migrations
cd frontend && npm test              # frontend unit tests
```

## What's in it so far

- Email sign-up and sign-in, onboarding (body, goal, experience, schedule, gyms and equipment)
- Exercise library with alternatives, favorites and hidden exercises
- Weekly planner for every common split, with skip and swap
- Workout logging, progression, readiness check-in and a safety layer
- Progress: weight trend and goal date, body fat and measurements, sets per muscle,
  strength curves, a recovery map, consistency, and progress photos that never leave
  the phone
- Works offline: opens with no signal, logs sets and check-ins on the phone, and syncs
  them when the connection is back
- Cardio and mat work: log any activity (treadmill speed and incline, machine levels,
  calories or an estimate, the floor moves you did), a weekly cardio target from your
  goal, warm-up, finisher and cool-down stretches, and "train at home on a mat today"
- AI coach: explains every target from your own data and proposes changes the engine
  checks before you can apply them (Groq, Gemini as backup, rule-based without either)

## Docs

- [Planner](docs/PLANNER.md) · [Training](docs/TRAINING.md) · [Progress](docs/PROGRESS.md) · [Offline](docs/OFFLINE.md) · [Coach](docs/COACH.md) · [Cardio](docs/CARDIO.md)
- [Deploying](docs/DEPLOY.md) · [Licenses](docs/LICENSES.md) · [Backlog](docs/BACKLOG.md)

_Full README (architecture, design decisions, evaluation results) to come._
