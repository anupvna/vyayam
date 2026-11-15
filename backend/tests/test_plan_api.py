from datetime import date

from tests.conftest import UserFactory

MONDAY = "2026-11-16"
PROFILE = {
    "birth_year": date.today().year - 24,
    "sex": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "experience": "intermediate",
    "goal": "muscle_gain",
    "training_days": [0, 2, 4],
    "session_minutes": 60,
    "injury_areas": [],
}
FULL_GYM = [
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


async def _ready(client, split: str = "ppl", **profile) -> None:
    await client.put("/api/profile", json=PROFILE | profile)
    await client.post("/api/gyms", json={"name": "Gym", "equipment": FULL_GYM})
    resp = await client.put("/api/plan/split", json={"split_id": split, "today": MONDAY})
    assert resp.status_code == 200, resp.text


async def test_splits_need_a_profile_then_recommend(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    assert (await me.get("/api/plan/splits")).status_code == 404
    await me.put("/api/profile", json=PROFILE)
    body = (await me.get("/api/plan/splits")).json()
    assert body["recommended"] == "full_body" and body["reason"]
    assert body["current"] is None
    ids = {s["id"] for s in body["splits"]}
    assert {"full_body", "upper_lower", "ppl", "bro", "arnold", "chest_back_legs"} <= ids
    bro = next(s for s in body["splits"] if s["id"] == "bro")
    assert bro["fit_note"]  # built for 5 days, user trains 3


async def test_week_follows_the_split(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    week = (await me.get(f"/api/plan/week?today={MONDAY}")).json()
    assert [d["session_name"] for d in week["days"] if d["status"] == "planned"] == [
        "Push",
        "Pull",
        "Legs",
    ]
    assert [d["status"] for d in week["days"]] == [
        "planned",
        "rest",
        "planned",
        "rest",
        "planned",
        "rest",
        "rest",
    ]
    assert week["split"]["id"] == "ppl"


async def test_week_needs_a_split(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    assert (await me.get(f"/api/plan/week?today={MONDAY}")).status_code == 404


async def test_today_and_time_boxed_today(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl", session_minutes=90)
    full = (await me.get(f"/api/plan/today?today={MONDAY}")).json()
    assert full["status"] == "planned" and full["exercises"]
    short = (await me.get(f"/api/plan/today?today={MONDAY}&minutes=30")).json()
    assert short["minutes"] <= 30 < full["minutes"] or full["minutes"] <= 30
    assert short["exercises"][0]["exercise_id"] == full["exercises"][0]["exercise_id"]
    rest = (await me.get("/api/plan/today?today=2026-11-17")).json()
    assert rest["status"] == "rest" and rest["exercises"] == []


async def test_skip_moves_the_session_and_restore_undoes_it(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    resp = await me.post(f"/api/plan/days/{MONDAY}/skip", json={"today": MONDAY})
    assert resp.status_code == 200
    week = resp.json()
    assert week["days"][0]["status"] == "skipped"
    assert len([d for d in week["days"] if d["status"] == "planned"]) == 2  # no cramming
    assert week["notes"]

    assert (await me.delete(f"/api/plan/days/{MONDAY}")).status_code == 204
    week = (await me.get(f"/api/plan/week?today={MONDAY}")).json()
    assert week["days"][0]["session_name"] == "Push"


async def test_swap_to_another_session_and_freestyle(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    week = (
        await me.post(
            f"/api/plan/days/{MONDAY}/swap", json={"session_key": "legs", "today": MONDAY}
        )
    ).json()
    assert week["days"][0]["session_name"] == "Legs" and week["days"][0]["swapped"]
    later = sorted(d["session_name"] for d in week["days"][1:] if d["status"] == "planned")
    assert later == ["Pull", "Push"]

    week = (
        await me.post(
            f"/api/plan/days/{MONDAY}/swap", json={"muscles": ["chest", "biceps"], "today": MONDAY}
        )
    ).json()
    assert week["days"][0]["session_name"] == "Your pick"


async def test_bad_swaps_and_rest_days_are_rejected(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    tuesday = "2026-11-17"
    assert (
        await me.post(f"/api/plan/days/{tuesday}/skip", json={"today": MONDAY})
    ).status_code == 409
    assert (
        await me.post(
            f"/api/plan/days/{MONDAY}/swap", json={"session_key": "arms", "today": MONDAY}
        )
    ).status_code == 422
    assert (
        await me.post(f"/api/plan/days/{MONDAY}/swap", json={"today": MONDAY})
    ).status_code == 422
    assert (
        await me.post(
            f"/api/plan/days/{MONDAY}/swap", json={"muscles": ["spleen"], "today": MONDAY}
        )
    ).status_code == 422
    assert (
        await me.post("/api/plan/days/2026-11-02/skip", json={"today": MONDAY})
    ).status_code == 409  # a past week


async def test_custom_split(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await me.post("/api/gyms", json={"name": "Gym", "equipment": FULL_GYM})
    custom = [
        {"name": "Chest and biceps", "muscles": ["chest", "biceps"]},
        {"name": "Back and triceps", "muscles": ["lats", "upper_back", "triceps"]},
        {"name": "Legs", "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    ]
    resp = await me.put(
        "/api/plan/split", json={"split_id": "custom", "custom_sessions": custom, "today": MONDAY}
    )
    assert resp.status_code == 200
    week = (await me.get(f"/api/plan/week?today={MONDAY}")).json()
    assert [d["session_name"] for d in week["days"] if d["status"] == "planned"] == [
        "Chest and biceps",
        "Back and triceps",
        "Legs",
    ]
    bad = await me.put("/api/plan/split", json={"split_id": "custom", "today": MONDAY})
    assert bad.status_code == 422
    unknown = await me.put("/api/plan/split", json={"split_id": "yolo", "today": MONDAY})
    assert unknown.status_code == 422


async def test_changing_split_clears_future_changes(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    await me.post(f"/api/plan/days/{MONDAY}/skip", json={"today": MONDAY})
    await me.put("/api/plan/split", json={"split_id": "full_body", "today": MONDAY})
    week = (await me.get(f"/api/plan/week?today={MONDAY}")).json()
    assert week["days"][0]["status"] == "planned"


async def test_plan_requires_csrf_for_changes(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _ready(me, "ppl")
    del me.headers["X-CSRF-Token"]
    assert (
        await me.post(f"/api/plan/days/{MONDAY}/skip", json={"today": MONDAY})
    ).status_code == 403


async def test_plans_are_private(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await _ready(alice, "ppl")
    await _ready(bob, "ppl")
    await alice.post(f"/api/plan/days/{MONDAY}/skip", json={"today": MONDAY})
    bob_week = (await bob.get(f"/api/plan/week?today={MONDAY}")).json()
    assert bob_week["days"][0]["status"] == "planned"  # Alice's skip isn't Bob's
    await bob.delete(f"/api/plan/days/{MONDAY}")  # Bob can't undo Alice's skip either
    alice_week = (await alice.get(f"/api/plan/week?today={MONDAY}")).json()
    assert alice_week["days"][0]["status"] == "skipped"
