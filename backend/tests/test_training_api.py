import uuid
from datetime import date

from tests.conftest import UserFactory

MONDAY, WEDNESDAY, FRIDAY = "2026-11-16", "2026-11-18", "2026-11-20"
PROFILE = {
    "birth_year": date.today().year - 24,
    "sex": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "experience": "intermediate",
    "goal": "muscle_gain",
    "training_days": [0, 2, 4],
    "session_minutes": 75,
    "injury_areas": [],
}
GYM = [
    "barbell",
    "dumbbells",
    "squat_rack",
    "flat_bench",
    "adjustable_bench",
    "pull_up_bar",
    "cable_station",
    "lat_pulldown",
    "leg_press",
    "leg_curl",
    "leg_extension",
]
GOOD = {"sleep": 5, "energy": 5, "stress": 1}


async def _ready(client) -> None:
    await client.put("/api/profile", json=PROFILE)
    await client.post("/api/gyms", json={"name": "Gym", "equipment": GYM})
    await client.put("/api/plan/split", json={"split_id": "full_body", "today": MONDAY})


async def _today(client, day: str = MONDAY, **params) -> dict:
    q = "&".join(f"{k}={v}" for k, v in params.items())
    resp = await client.get(f"/api/training/today?today={day}&{q}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _set(exercise_id: str, weight: float, reps: int, index: int = 1, day: str = MONDAY, **kw):
    return {
        "id": str(uuid.uuid4()),
        "day": day,
        "exercise_id": exercise_id,
        "set_index": index,
        "weight_kg": weight,
        "reps": reps,
    } | kw


# ---------------------------------------------------------------- readiness and safety


async def test_no_check_in_yet(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    assert (await me.get(f"/api/readiness?today={MONDAY}")).status_code == 404
    today = await _today(me)
    assert today["readiness"] is None and not today["stop"] and today["exercises"]


async def test_red_flag_stops_training(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    resp = await me.post(
        "/api/readiness", json={"today": MONDAY, **GOOD, "red_flags": ["chest_pain"]}
    )
    assert resp.json()["verdict"] == "stop"
    today = await _today(me)
    assert today["stop"] is True
    assert today["day"]["exercises"] == [] and today["exercises"] == []
    assert "emergency" in today["readiness"]["messages"][0]


async def test_pain_removes_exercises_loading_that_area(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    before = await _today(me)
    await me.post("/api/readiness", json={"today": MONDAY, **GOOD, "pain_areas": ["knee"]})
    after = await _today(me)
    lib = {e["id"]: e for e in (await me.get("/api/exercises")).json()}
    loads = {
        e["exercise_id"]: (await me.get(f"/api/exercises/{e['exercise_id']}")).json()["loads"]
        for e in after["day"]["exercises"]
    }
    assert all("knee" not in v for v in loads.values())
    assert [e["exercise_id"] for e in before["day"]["exercises"]] != list(loads)
    assert lib  # library still loads


async def test_low_readiness_makes_the_day_lighter(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    normal = await _today(me)
    await me.post("/api/readiness", json={"today": MONDAY, "sleep": 3, "energy": 3, "stress": 3})
    lighter = await _today(me)
    assert lighter["readiness"]["verdict"] == "lighter"
    assert sum(e["sets"] for e in lighter["day"]["exercises"]) < sum(
        e["sets"] for e in normal["day"]["exercises"]
    )


async def test_very_low_readiness_suggests_rest_with_an_easy_option(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    await me.post("/api/readiness", json={"today": MONDAY, "sleep": 1, "energy": 1, "stress": 5})
    today = await _today(me)
    assert today["suggest_rest"] and all(e["light"] for e in today["day"]["exercises"])


async def test_run_down_check_ins_trigger_a_deload(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    for d in ("2026-11-14", "2026-11-15", MONDAY):
        await me.post("/api/readiness", json={"today": d, "sleep": 2, "energy": 2, "stress": 4})
    week = (await me.get(f"/api/plan/week?today={MONDAY}")).json()
    assert week["deload"] and "run down" in week["notes"][0]


async def test_bad_check_in_input(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    for bad in (
        {"sleep": 0},
        {"red_flags": ["sneezing"]},
        {"pain_areas": ["soul"]},
        {"sore_areas": ["eyebrows"]},
    ):
        resp = await me.post("/api/readiness", json={"today": MONDAY, **GOOD} | bad)
        assert resp.status_code == 422


# ---------------------------------------------------------------- logging


async def test_replayed_set_is_never_duplicated(make_user: UserFactory, pool) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    s = _set("bench_press", 60, 8)
    first = await me.post("/api/logs", json=s)
    assert first.status_code == 201
    for _ in range(5):  # flaky gym Wi-Fi: the app retries the same set
        again = await me.post("/api/logs", json=s)
        assert again.status_code == 200 and again.json()["id"] == s["id"]
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM set_logs") == 1


async def test_someone_elses_set_id_is_refused(make_user: UserFactory, pool) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await _ready(alice)
    s = _set("bench_press", 60, 8)
    await alice.post("/api/logs", json=s)
    resp = await bob.post("/api/logs", json=s | {"weight_kg": 200})
    assert resp.status_code == 409
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT weight_kg FROM set_logs") == 60  # untouched


async def test_prs_are_detected(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    first = (await me.post("/api/logs", json=_set("bench_press", 60, 8))).json()
    same = (await me.post("/api/logs", json=_set("bench_press", 60, 8, 2))).json()
    better = (await me.post("/api/logs", json=_set("bench_press", 62.5, 8, 3))).json()
    assert not first["pr"] and not same["pr"] and better["pr"]
    assert better["e1rm"] == 79.2
    history = (await me.get("/api/exercises/bench_press/history")).json()
    assert len(history) == 1 and history[0]["best_e1rm"] == 79.2


async def test_progression_carries_into_the_next_session(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    monday = await _today(me)
    main = monday["day"]["exercises"][0]
    assert monday["exercises"][0]["target"]["change"] == "first"
    lo, hi = main["reps"]
    for i in range(main["sets"]):  # hit the top of the range on every set
        await me.post("/api/logs", json=_set(main["exercise_id"], 60, hi, i + 1))
    friday = await _today(me, FRIDAY)  # full body A again
    target = next(e for e in friday["exercises"] if e["exercise_id"] == main["exercise_id"])
    assert target["target"]["change"] == "increase" and target["target"]["weight_kg"] > 60
    logged_monday = await _today(me)
    assert len(logged_monday["exercises"][0]["logged"]) == main["sets"]


async def test_last_session_is_shown_set_by_set(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    monday = await _today(me)
    first = monday["exercises"][0]
    assert first["last"] is None and first["load"] == "barbell_lower"
    main = first["exercise_id"]
    # A pyramid, plus one more set than planned: both are fine.
    weights = [60, 65, 70, 72.5]
    for i, w in enumerate(weights):
        await me.post("/api/logs", json=_set(main, w, 8, i + 1))
    friday = next(e for e in (await _today(me, FRIDAY))["exercises"] if e["exercise_id"] == main)
    assert friday["last"]["day"] == MONDAY
    assert [x["weight_kg"] for x in friday["last"]["sets"]] == weights
    assert friday["target"]["weight_kg"] == 72.5  # progression follows the heaviest set


async def test_load_tells_dumbbells_from_bodyweight(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    loads = {e["load"] for e in (await _today(me))["exercises"]}
    assert loads <= {
        "barbell_lower",
        "barbell_upper",
        "dumbbell",
        "machine_lower",
        "machine_upper",
        None,
    }


async def test_week_shows_logged_days_and_delete_works(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    s = _set("bench_press", 60, 8)
    await me.post("/api/logs", json=s)
    week = (await me.get(f"/api/plan/week?today={WEDNESDAY}")).json()
    assert week["days"][0]["logged_sets"] == 1
    assert (await me.delete(f"/api/logs/{s['id']}")).status_code == 204
    assert (await me.get(f"/api/logs?day={MONDAY}")).json() == []


async def test_bad_sets_are_rejected(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me)
    for bad in ({"exercise_id": "moonwalk"}, {"reps": -1}, {"weight_kg": 5000}, {"set_index": 0}):
        assert (
            await me.post("/api/logs", json=_set("bench_press", 60, 8) | bad)
        ).status_code == 422


async def test_logs_and_check_ins_are_private(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await _ready(alice)
    await _ready(bob)
    s = _set("bench_press", 60, 8)
    await alice.post("/api/logs", json=s)
    await alice.post("/api/readiness", json={"today": MONDAY, **GOOD, "pain_areas": ["knee"]})

    assert (await bob.get(f"/api/logs?day={MONDAY}")).json() == []
    assert (await bob.get(f"/api/readiness?today={MONDAY}")).status_code == 404
    assert (await bob.get("/api/exercises/bench_press/history")).json() == []
    await bob.delete(f"/api/logs/{s['id']}")  # silently does nothing to Alice's set
    assert len((await alice.get(f"/api/logs?day={MONDAY}")).json()) == 1


async def test_logging_requires_csrf(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    del me.headers["X-CSRF-Token"]
    assert (await me.post("/api/logs", json=_set("bench_press", 60, 8))).status_code == 403
