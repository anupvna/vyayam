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

_Full README (architecture, design decisions, evaluation results) to come._
