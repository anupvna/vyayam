# Vyayam

A personal gym coach that runs as an installable web app (PWA). A deterministic,
tested engine decides training plans, progression, recovery and body calculations.
An AI coach explains and adapts, and every change it proposes is checked by the
engine's rules before it is shown.

> Training aid, not medical advice.

## Run locally

Requirements: Docker, Python 3.12.

```bash
docker compose up -d                 # Postgres on localhost:5433
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"

cd backend
python -m app.migrate                # create tables
uvicorn app.main:app --reload        # http://localhost:8000/api/health
pytest                               # run tests
```

_Full README (architecture, design decisions, evaluation results) to come._
