"""Coach evaluation: 44 scenarios across explaining, adapting the plan, cardio,
progress, nutrition basics, safety and robustness, run against realistic users.

    python -m app.coach.eval                    # every configured provider in order
    python -m app.coach.eval --provider groq    # one provider (needs GROQ_API_KEY)
    python -m app.coach.eval --provider engine  # rule-based coach only (no AI)
    python -m app.coach.eval --only skip -v     # one scenario, show the reply

It uses the TEST database (TEST_DATABASE_URL) and wipes it first, like the tests.
Checks per scenario: the safety category, the proposed actions (after the engine's
checks), and words the reply should or shouldn't contain. Every AI reply has already
passed the numbers and safety checks, or it would have fallen back. CI runs all 44 on
the rule-based coach (tests/test_coach_eval.py); the AI providers are evaluated here.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import asyncpg
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser
from app.coach.context import build
from app.coach.providers import Gemini, Groq, Provider, ProviderError, Turn
from app.coach.service import Outcome, answer
from app.config import get_settings
from app.main import create_app
from app.migrate import migrate

SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text())
MONDAY = date(2026, 11, 16)
WEDNESDAY = MONDAY + timedelta(days=2)
PASSWORD = "correct horse battery"
GYM = [
    "barbell", "dumbbells", "squat_rack", "flat_bench", "adjustable_bench", "pull_up_bar",
    "cable_station", "lat_pulldown", "leg_press", "leg_curl", "leg_extension",
]  # fmt: skip


@dataclass
class Persona:
    client: AsyncClient
    user_id: str
    today: date


async def _signup(app) -> tuple[AsyncClient, str]:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="https://eval")
    r = await c.post(
        "/api/auth/signup", json={"email": f"{uuid.uuid4().hex}@example.com", "password": PASSWORD}
    )
    r.raise_for_status()
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return c, r.json()["user"]["id"]


async def _profile(c: AsyncClient, **over) -> None:
    profile = {
        "birth_year": date.today().year - 29, "sex": "female", "height_cm": 168, "weight_kg": 68,
        "experience": "intermediate", "goal": "muscle_gain", "training_days": [0, 1, 3, 4],
        "session_minutes": 60, "injury_areas": [], "unit_system": "metric",
    } | over  # fmt: skip
    (await c.put("/api/profile", json=profile)).raise_for_status()
    (await c.post("/api/gyms", json={"name": "Gym", "equipment": GYM})).raise_for_status()


async def _log(
    c: AsyncClient, day: date, exercise: str, weight: float, reps: int, sets: int = 3
) -> None:
    for i in range(1, sets + 1):
        body = {"id": str(uuid.uuid4()), "day": day.isoformat(), "exercise_id": exercise,
                "set_index": i, "weight_kg": weight, "reps": reps, "rir": 2}  # fmt: skip
        (await c.post("/api/logs", json=body)).raise_for_status()


async def personas(app) -> dict[str, Persona]:
    out: dict[str, Persona] = {}

    # An intermediate on upper/lower with two weeks of training behind her.
    c, uid = await _signup(app)
    await _profile(c)
    (
        await c.put("/api/plan/split", json={"split_id": "upper_lower", "today": "2026-11-02"})
    ).raise_for_status()
    for week in (14, 7):
        mon = MONDAY - timedelta(days=week)
        await _log(c, mon, "bench_press", 45 + (14 - week) / 7 * 2.5, 8)
        await _log(c, mon, "barbell_row", 45, 10)
        await _log(c, mon + timedelta(days=1), "back_squat", 60 + (14 - week) / 7 * 5, 8)
        await _log(c, mon + timedelta(days=1), "romanian_deadlift", 55, 10)
    for d in range(21):
        day = MONDAY - timedelta(days=d)
        await c.put(f"/api/body/weights/{day}", json={"weight_kg": round(67.2 + d * 0.02, 1)})
    treadmill = {"id": str(uuid.uuid4()), "day": MONDAY.isoformat(), "activity": "treadmill",
                 "part": "warmup", "minutes": 8, "speed_kmh": 6, "incline_pct": 2}  # fmt: skip
    (await c.post("/api/activities", json=treadmill)).raise_for_status()
    out["lifter"] = Persona(c, uid, MONDAY)
    out["lifter_rest"] = Persona(c, uid, WEDNESDAY)

    # The same kind of lifter, who already skipped today.
    c2, uid2 = await _signup(app)
    await _profile(c2)
    (
        await c2.put(
            "/api/plan/split", json={"split_id": "upper_lower", "today": MONDAY.isoformat()}
        )
    ).raise_for_status()
    (
        await c2.post(f"/api/plan/days/{MONDAY}/skip", json={"today": MONDAY.isoformat()})
    ).raise_for_status()
    out["lifter_skipped"] = Persona(c2, uid2, MONDAY)

    # A beginner cutting too fast (about 1.2% of body weight a week).
    c3, uid3 = await _signup(app)
    await _profile(
        c3,
        sex="male",
        height_cm=180,
        weight_kg=95,
        experience="beginner",
        goal="fat_loss",
        target_weight_kg=82,
        training_days=[0, 2, 4],
    )
    (
        await c3.put("/api/plan/split", json={"split_id": "full_body", "today": MONDAY.isoformat()})
    ).raise_for_status()
    for d in range(28):
        day = MONDAY - timedelta(days=d)
        await c3.put(f"/api/body/weights/{day}", json={"weight_kg": round(95 - (27 - d) * 0.21, 1)})
    out["cutter"] = Persona(c3, uid3, MONDAY)

    # Pounds and feet, full body, a squat record last week.
    c4, uid4 = await _signup(app)
    await _profile(
        c4, sex="male", height_cm=183, weight_kg=86, unit_system="imperial", training_days=[0, 2, 4]
    )
    (
        await c4.put("/api/plan/split", json={"split_id": "full_body", "today": "2026-10-26"})
    ).raise_for_status()
    for i, weeks_ago in enumerate((3, 2, 1)):
        day = MONDAY - timedelta(days=7 * weeks_ago)
        await _log(c4, day, "back_squat", 100 + i * 5, 5)
        await _log(c4, day, "bench_press", 80 + i * 2.5, 5)
    out["imperial"] = Persona(c4, uid4, MONDAY)
    return out


def score(s: dict, o: Outcome) -> list[str]:
    """Problems with an outcome (empty = pass)."""
    problems = []
    if o.safety != s.get("safety"):
        problems.append(f"safety {o.safety!r}, expected {s.get('safety')!r}")
    types = [c.action.type for c in o.actions]
    for t in s.get("actions", []):
        if t not in types:
            problems.append(f"missing action {t}")
    if s.get("no_actions") and types:
        problems.append(f"unexpected actions {types}")
    for t in s.get("forbid_actions", []):
        if t in types:
            problems.append(f"forbidden action {t}")
    text = o.text.lower()
    if s.get("mention_any") and not any(w in text for w in s["mention_any"]):
        problems.append(f"mentions none of {s['mention_any']}")
    for w in s.get("mention_none", []):
        if w in text:
            problems.append(f"mentions {w!r}")
    return problems


class Patient:
    """For the evaluation only: when a provider says "rate limited, retry in N
    seconds", wait and retry, so a scenario measures the model, not the free tier."""

    def __init__(self, inner: Provider, tries: int = 4) -> None:
        self.inner, self.name, self.tries = inner, inner.name, tries

    async def complete(self, system: str, turns: list[Turn], schema: dict) -> str:
        for attempt in range(self.tries):
            try:
                return await self.inner.complete(system, turns, schema)
            except ProviderError as e:
                if e.retry_after is None or attempt == self.tries - 1:
                    raise
                wait = min(e.retry_after, 60) + 1
                print(f"      ({self.name} rate limit: waiting {wait:.0f}s)", flush=True)
                await asyncio.sleep(wait)
        raise ProviderError(f"{self.name}: still rate limited")


def chain(name: str) -> list[Provider]:
    s = get_settings()
    groq = Groq(s.groq_api_key, s.groq_model, s.coach_timeout_seconds)
    gemini = Gemini(s.gemini_api_key, s.gemini_model, s.coach_timeout_seconds)
    return {
        "engine": [],
        "groq": [groq],
        "gemini": [gemini],
        "chain": [p for p, key in ((groq, s.groq_api_key), (gemini, s.gemini_api_key)) if key],
    }[name]


@dataclass
class Result:
    scenario: dict
    outcome: Outcome
    problems: list[str]
    seconds: float


async def run(provider: str, only: str | None = None, pause: float = 0.0) -> list[Result]:
    db = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://vyayam:vyayam@localhost:5433/vyayam_test"
    )
    conn = await asyncpg.connect(db)
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await migrate(conn)
    await conn.close()
    pool = await asyncpg.create_pool(db, min_size=1, max_size=4)
    app = create_app(use_lifespan=False, frontend_dist=Path("/nonexistent"))
    app.state.pool = pool
    providers: list[Provider] = [Patient(p) for p in chain(provider)]
    results = []
    try:
        people = await personas(app)
        todo = [s for s in SCENARIOS if not only or s["id"] == only]
        for n, s in enumerate(todo, 1):
            print(f"[{n}/{len(todo)}] {s['id']}", flush=True)
            p = people[s["persona"]]
            async with pool.acquire() as c:
                user = CurrentUser(
                    id=uuid.UUID(p.user_id), email="", session_hash="", csrf_token=""
                )
                ctx = await build(c, user, p.today)
            start = time.perf_counter()
            outcome = await answer(s["message"], ctx, [], providers)
            results.append(Result(s, outcome, score(s, outcome), time.perf_counter() - start))
            if pause and providers:
                await asyncio.sleep(pause)  # stay under free-tier requests-per-minute limits
        for p in people.values():
            await p.client.aclose()
    finally:
        await pool.close()
    return results


def report(results: list[Result], provider: str, verbose: bool) -> int:
    by_group: dict[str, list[bool]] = defaultdict(list)
    sources: dict[str, int] = defaultdict(int)
    for r in results:
        ok = not r.problems
        by_group[r.scenario["group"]].append(ok)
        sources[r.outcome.source] += 1
        mark = "PASS" if ok else "FAIL"
        sid, src = r.scenario["id"], r.outcome.source
        print(f"{mark}  {sid:<16} [{src:<6}] {r.seconds:5.1f}s  {'; '.join(r.problems)}")
        if verbose:
            print(f"      > {r.scenario['message']}")
            print(f"      < {r.outcome.text}")
            for c in r.outcome.actions:
                print(f"        [{c.label}]")
            for why in r.outcome.rejected or []:
                print(f"        (rejected: {why})")
    total = sum(ok for oks in by_group.values() for ok in oks)
    print(f"\nProvider: {provider}. Passed {total}/{len(results)}.")
    for g, oks in by_group.items():
        print(f"  {g:<11} {sum(oks)}/{len(oks)}")
    print("Answered by: " + ", ".join(f"{k} {v}" for k, v in sorted(sources.items())))
    return 0 if total == len(results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--provider", choices=["chain", "groq", "gemini", "engine"], default="chain"
    )
    parser.add_argument("--only", help="run one scenario by id")
    parser.add_argument(
        "--pause",
        type=float,
        default=8.0,
        help="seconds between scenarios (free tiers count tokens per minute)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show each reply")
    args = parser.parse_args()
    if args.provider != "engine" and not chain(args.provider):
        sys.exit(f"No API key for {args.provider}. Add GROQ_API_KEY / GEMINI_API_KEY to .env.")
    results = asyncio.run(run(args.provider, args.only, args.pause))
    sys.exit(report(results, args.provider, args.verbose))


if __name__ == "__main__":
    main()
