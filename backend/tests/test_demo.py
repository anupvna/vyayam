"""The demo account seed: realistic data through the real API, and safe to re-run."""

from datetime import date

import asyncpg

from app.demo import DEMO_EMAIL, seed
from tests.conftest import TEST_DATABASE_URL, UserFactory

TODAY = date(2026, 11, 18)  # a Wednesday


async def _counts(conn: asyncpg.Connection) -> dict:
    uid = await conn.fetchval("SELECT id FROM users WHERE email = $1", DEMO_EMAIL)
    return {
        t: await conn.fetchval(f"SELECT count(*) FROM {t} WHERE user_id = $1", uid)
        for t in ("set_logs", "readiness_checkins", "body_weights", "activity_logs")
    }


async def test_demo_seed_builds_a_lived_in_account(
    pool: asyncpg.Pool, make_user: UserFactory
) -> None:
    other = await make_user("someone@example.com")  # a real user must be left alone
    counts = await seed(TEST_DATABASE_URL, today=TODAY)
    assert counts["sets"] > 150 and counts["check_ins"] >= 12
    assert counts["weigh_ins"] > 15 and counts["activities"] > 15

    async with pool.acquire() as conn:
        first = await _counts(conn)
        assert first["set_logs"] == counts["sets"]
        await seed(TEST_DATABASE_URL, today=TODAY)  # re-run: reset, not duplicate
        assert await _counts(conn) == first
        assert await conn.fetchval("SELECT count(*) FROM users WHERE email = $1", DEMO_EMAIL) == 1
    assert (await other.get("/api/auth/me")).status_code == 200


async def test_demo_targets_progress(pool: asyncpg.Pool) -> None:
    await seed(TEST_DATABASE_URL, today=TODAY)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT l.day, max(l.weight_kg) AS w FROM set_logs l JOIN users u ON u.id = l.user_id
               WHERE u.email = $1 AND l.exercise_id = (
                   SELECT exercise_id FROM set_logs l2 JOIN users u2 ON u2.id = l2.user_id
                   WHERE u2.email = $1 AND l2.weight_kg > 0
                   GROUP BY exercise_id ORDER BY count(*) DESC LIMIT 1)
               GROUP BY l.day ORDER BY l.day""",
            DEMO_EMAIL,
        )
    weights = [float(r["w"]) for r in rows]
    assert len(weights) >= 4
    # The engine raised the load once every set hit the top of the range (a later
    # deload week may bring it back down, so compare the peak, not the last day).
    assert max(weights) > weights[0]
