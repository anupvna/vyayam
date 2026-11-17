"""Create, or reset, the public demo account with four weeks of realistic data.

    cd backend
    DATABASE_URL='postgresql://...' python -m app.demo

It touches only the demo user: that account (and everything it owns) is deleted and
rebuilt through the app's own API, so every number comes from the real engine. Run it
again any time to wipe what visitors changed. The demo password is public on purpose
(it's in the README); override it with DEMO_PASSWORD.

What it creates: an intermediate lifter on upper/lower four days a week, with logged
sets that progress, daily check-ins, a skipped session, weigh-ins trending down,
measurements every two weeks, warm-ups, walks, bike sessions and a mat workout.
Today's session is left unlogged so a visitor can try logging a set.
"""

import argparse
import asyncio
import os
import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app

DEMO_EMAIL = get_settings().demo_email
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "vyayam-demo-2026")
WEEKS = 4  # intermediate deloads fall in week 5: keep the demo on a clean upward run
# Equipment you put a number of kilos on. Everything else (pull-up bar, ab wheel, mat,
# bands...) is logged as bodyweight.
LOADED = {
    "barbell", "dumbbells", "ez_bar", "kettlebells", "trap_bar", "smith_machine",
    "cable_station", "lat_pulldown", "cable_row", "leg_press", "hack_squat",
    "leg_extension", "leg_curl", "calf_raise_machine", "hip_thrust_machine",
    "chest_press_machine", "pec_deck", "shoulder_press_machine", "row_machine",
    "medicine_ball",
}  # fmt: skip


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def _ok(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text}")
    return r.json() if r.content else None


async def seed(database_url: str, today: date | None = None, seed: int = 7) -> dict:
    today = today or date.today()
    rng = random.Random(seed)
    start = _monday(today) - timedelta(weeks=WEEKS - 1)

    conn = await asyncpg.connect(database_url)
    try:  # every table hangs off users with ON DELETE CASCADE
        await conn.execute("DELETE FROM users WHERE email = $1", DEMO_EMAIL)
    finally:
        await conn.close()

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
    app = create_app(use_lifespan=False, frontend_dist=Path("/nonexistent"))
    app.state.pool = pool
    app.state.coach_providers = []
    counts = {"sets": 0, "check_ins": 0, "weigh_ins": 0, "activities": 0}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://demo") as c:
            r = await _ok(
                await c.post(
                    "/api/auth/signup", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
                )
            )
            c.headers["X-CSRF-Token"] = r["csrf_token"]
            await _ok(
                await c.put(
                    "/api/profile",
                    json={
                        "birth_year": today.year - 28,
                        "sex": "male",
                        "height_cm": 178,
                        "weight_kg": 84,
                        "experience": "intermediate",
                        "goal": "fat_loss",
                        "target_weight_kg": 78,
                        "training_days": [0, 1, 3, 4],
                        "session_minutes": 60,
                        "injury_areas": [],
                        "unit_system": "metric",
                    },
                )
            )
            catalog = await _ok(await c.get("/api/catalog"))
            commercial = next(p for p in catalog["presets"] if p["id"] == "commercial")
            await _ok(
                await c.post(
                    "/api/gyms", json={"name": "City gym", "equipment": commercial["equipment"]}
                )
            )
            await _ok(
                await c.put(
                    "/api/plan/split", json={"split_id": "upper_lower", "today": str(start)}
                )
            )
            library = {e["id"]: e for e in await _ok(await c.get("/api/exercises"))}

            def start_weight(ex_id: str, kind: str) -> float:
                options = library[ex_id]["equipment"]
                if [] in options or not any(LOADED & set(o) for o in options):
                    return 0  # bodyweight
                machine = any({"cable_station", "lat_pulldown", "cable_row"} & set(o) or
                              any(e.endswith(("_machine", "press", "curl", "extension", "deck"))
                                  for e in o) for o in options)  # fmt: skip
                return 50 if kind == "main" else 30 if machine else 15

            skipped = start + timedelta(days=7 + 3)  # one missed Thursday, like real life
            day = start
            while day <= today:
                d = str(day)
                # Weigh-ins most mornings, trending down about 0.5 kg a week.
                if rng.random() < 0.8:
                    i = (day - start).days
                    w = round(84.2 - 0.075 * i + rng.uniform(-0.35, 0.35), 1)
                    await _ok(await c.put(f"/api/body/weights/{d}", json={"weight_kg": w}))
                    counts["weigh_ins"] += 1
                if (day - start).days in (0, 14, (today - start).days):
                    shrink = (day - start).days / 14 * 0.8
                    await _ok(
                        await c.put(
                            f"/api/body/measurements/{d}",
                            json={
                                "neck_cm": 39,
                                "waist_cm": round(91 - shrink, 1),
                                "chest_cm": 103,
                                "arm_cm": 36.5,
                                "thigh_cm": 58,
                            },
                        )
                    )

                week = await _ok(await c.get(f"/api/plan/today?today={d}"))
                training = week["status"] == "planned" and day != skipped
                if training:
                    await _ok(
                        await c.post(
                            "/api/readiness",
                            json={
                                "today": d,
                                "sleep": rng.choice([3, 4, 4, 5]),
                                "energy": rng.choice([3, 4, 4, 5]),
                                "stress": rng.choice([1, 2, 2, 3]),
                                "sore_areas": [],
                            },
                        )
                    )
                    counts["check_ins"] += 1
                if training and day < today:  # today stays open for the visitor
                    t = await _ok(await c.get(f"/api/training/today?today={d}"))
                    await _ok(
                        await c.post(
                            "/api/activities",
                            json={"id": str(uuid.uuid4()), "day": d, "activity": "treadmill",
                                  "part": "warmup", "minutes": 5, "intensity": "easy",
                                  "speed_kmh": 5.5},
                        )
                    )  # fmt: skip
                    counts["activities"] += 1
                    for ex, x in zip(t["day"]["exercises"], t["exercises"], strict=True):
                        lo, hi = ex["reps"]
                        target = x["target"]
                        weight = target["weight_kg"] or start_weight(ex["exercise_id"], ex["kind"])
                        base = target["reps"] or lo
                        # Beat the target by a rep or two on good days: once every set
                        # hits the top of the range, the engine adds weight next time.
                        bump = rng.choice([0, 1, 1, 2])
                        for s in range(1, ex["sets"] + 1):
                            reps = min(hi, max(lo, base + bump))
                            await _ok(
                                await c.post(
                                    "/api/logs",
                                    json={"id": str(uuid.uuid4()), "day": d,
                                          "exercise_id": ex["exercise_id"], "set_index": s,
                                          "weight_kg": weight, "reps": reps, "rir": 2},
                                )
                            )  # fmt: skip
                            counts["sets"] += 1
                # Cardio on two rest days a week, and a mat workout now and then.
                extra = None
                if day.weekday() == 2:
                    extra = {"activity": "walk", "minutes": 35, "speed_kmh": 5.5}
                elif day.weekday() == 5:
                    extra = {"activity": "bike", "minutes": 25, "level": 8}
                elif day.weekday() == 6 and (day - start).days % 14 == 6:
                    extra = {"activity": "mat_workout", "minutes": 15,
                             "items": ["crunch", "plank", "bird_dog", "glute_bridge"]}  # fmt: skip
                if extra and day < today:
                    body = {"id": str(uuid.uuid4()), "day": d} | extra
                    await _ok(await c.post("/api/activities", json=body))
                    counts["activities"] += 1
                day += timedelta(days=1)
    finally:
        await pool.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--yes", action="store_true", help="don't ask before writing")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Set DATABASE_URL to the database to seed (e.g. the Neon connection string).")
    host = urlparse(url).hostname
    if not args.yes:
        answer = input(f"Reset {DEMO_EMAIL} on {host}? Other accounts are not touched. [y/N] ")
        if answer.strip().lower() != "y":
            sys.exit("Cancelled.")
    counts = asyncio.run(seed(url))
    print(
        f"Demo ready on {host}: {DEMO_EMAIL} / {DEMO_PASSWORD}\n"
        f"  {counts['sets']} sets, {counts['check_ins']} check-ins, "
        f"{counts['weigh_ins']} weigh-ins, {counts['activities']} activities"
    )


if __name__ == "__main__":
    main()
