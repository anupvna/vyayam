import uuid
from datetime import date, timedelta

from tests.conftest import UserFactory

MONDAY = date(2026, 11, 16)
PROFILE = {
    "birth_year": date.today().year - 24,
    "sex": "male",
    "height_cm": 180,
    "weight_kg": 85,
    "experience": "intermediate",
    "goal": "muscle_gain",
    "training_days": [0, 2, 4],
    "session_minutes": 60,
}


async def _log(client, day: date, exercise_id: str, weight: float, reps: int, n: int = 3) -> None:
    for i in range(n):
        resp = await client.post(
            "/api/logs",
            json={
                "id": str(uuid.uuid4()),
                "day": str(day),
                "exercise_id": exercise_id,
                "set_index": i + 1,
                "weight_kg": weight,
                "reps": reps,
            },
        )
        assert resp.status_code == 201


async def test_volume_counts_primary_and_secondary(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await _log(me, MONDAY, "bench_press", 60, 8)  # chest primary; triceps, front delts secondary
    v = (await me.get(f"/api/stats/volume?today={MONDAY}&weeks=4")).json()
    assert len(v["weeks"]) == 4 and v["weeks"][-1] == str(MONDAY)
    by = {m["muscle"]: m for m in v["muscles"]}
    assert by["chest"]["weekly"][-1] == 3 and by["triceps"]["weekly"][-1] == 1.5
    assert by["chest"]["target_low"] == 10 and by["chest"]["target_high"] == 16
    assert v["push_sets"] == 3 and v["pull_sets"] == 0


async def test_calendar_marks_done_missed_skipped_rest(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await me.post(
        "/api/gyms", json={"name": "Gym", "equipment": ["barbell", "flat_bench", "squat_rack"]}
    )
    await me.put("/api/plan/split", json={"split_id": "full_body", "today": str(MONDAY)})
    await _log(me, MONDAY, "bench_press", 60, 8, 1)
    await me.post(f"/api/plan/days/{MONDAY + timedelta(days=2)}/skip", json={"today": str(MONDAY)})
    friday = MONDAY + timedelta(days=4)
    cal = (await me.get(f"/api/stats/calendar?today={friday}&weeks=1")).json()
    status = {d["day"]: d["status"] for d in cal}
    assert status[str(MONDAY)] == "done"
    assert status[str(MONDAY + timedelta(days=1))] == "rest"
    assert status[str(MONDAY + timedelta(days=2))] == "skipped"
    assert status[str(friday)] == "upcoming"


async def test_recovery_map(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await _log(me, MONDAY, "back_squat", 100, 5)
    await _log(me, MONDAY - timedelta(days=2), "bench_press", 60, 8)
    await me.post(
        "/api/readiness",
        json={"today": str(MONDAY), "sleep": 4, "energy": 4, "stress": 2, "sore_areas": ["arms"]},
    )
    rec = {
        m["muscle"]: m["state"]
        for m in (await me.get(f"/api/stats/recovery?today={MONDAY}")).json()
    }
    assert rec["quads"] == "fatigued"  # squatted today
    assert rec["chest"] == "recovering"  # benched 2 days ago
    assert rec["biceps"] == "fatigued"  # sore arms
    assert rec["calves"] == "fresh"


async def test_weekly_summary_finds_prs(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await _log(me, MONDAY - timedelta(days=7), "bench_press", 60, 8)
    await _log(me, MONDAY, "bench_press", 65, 8)
    s = (await me.get(f"/api/stats/summary?today={MONDAY}")).json()
    assert s["prs"] == ["Barbell bench press"]
    assert s["sessions_done"] == 1 and s["sessions_planned"] == 3
    assert "chest" not in s["under_target"] or s["under_target"]
    assert any("New records" in line for line in s["lines"])


async def test_logged_exercises_list(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await _log(me, MONDAY - timedelta(days=7), "bench_press", 60, 8)
    await _log(me, MONDAY, "bench_press", 65, 8)
    await _log(me, MONDAY, "back_squat", 100, 5)
    ex = (await me.get("/api/stats/exercises")).json()
    assert [e["exercise_id"] for e in ex] == ["bench_press", "back_squat"]
    assert ex[0]["sessions"] == 2 and ex[0]["best_e1rm"] == 82.3


async def test_stats_are_private(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await alice.put("/api/profile", json=PROFILE)
    await bob.put("/api/profile", json=PROFILE)
    await _log(alice, MONDAY, "bench_press", 60, 8)
    v = (await bob.get(f"/api/stats/volume?today={MONDAY}")).json()
    assert all(sum(m["weekly"]) == 0 for m in v["muscles"])
    assert (await bob.get("/api/stats/exercises")).json() == []
