from datetime import date

from tests.conftest import UserFactory

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


async def _setup(client, equipment: list[str], injuries: list[str] | None = None) -> None:
    await client.put("/api/profile", json=PROFILE | {"injury_areas": injuries or []})
    await client.post("/api/gyms", json={"name": "Gym", "equipment": equipment})


async def test_library_requires_login(app) -> None:
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        assert (await c.get("/api/exercises")).status_code == 401


async def test_list_marks_availability_for_your_gym(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _setup(me, ["dumbbells"])
    items = {e["id"]: e for e in (await me.get("/api/exercises")).json()}
    assert items["dumbbell_curl"]["available"] is True
    assert items["leg_press"]["available"] is False
    assert items["push_up"]["available"] is True  # bodyweight is always available


async def test_detail_has_cues_and_alternatives(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _setup(me, ["barbell", "squat_rack", "leg_press", "smith_machine", "hack_squat"])
    body = (await me.get("/api/exercises/back_squat")).json()
    assert body["setup"] and body["mistakes"] and body["safety"]
    assert [a["id"] for a in body["alternatives"]] == ["leg_press", "smith_squat", "hack_squat"]


async def test_injuries_mark_exercises_unsafe_and_filter_alternatives(
    make_user: UserFactory,
) -> None:
    me = await make_user("a@example.com")
    await _setup(me, ["barbell", "squat_rack", "leg_press", "flat_bench"], injuries=["knee"])
    body = (await me.get("/api/exercises/back_squat")).json()
    assert body["safe"] is False
    assert body["injury_conflicts"] == ["knee"]  # only the injured area, not hip/back
    assert body["alternatives"]
    for alt in body["alternatives"]:
        assert alt["safe"] is True
        detail = (await me.get(f"/api/exercises/{alt['id']}")).json()
        assert "knee" not in detail["loads"]


async def test_favorite_hide_and_clear(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await _setup(me, ["barbell", "squat_rack", "leg_press", "smith_machine", "hack_squat"])
    url = "/api/exercises/leg_press/preference"

    assert (await me.put(url, json={"preference": "hidden"})).status_code == 200
    detail = (await me.get("/api/exercises/back_squat")).json()
    assert "leg_press" not in [a["id"] for a in detail["alternatives"]]

    await me.put(url, json={"preference": "favorite"})
    items = {e["id"]: e for e in (await me.get("/api/exercises")).json()}
    assert items["leg_press"]["preference"] == "favorite"

    await me.put(url, json={"preference": "none"})
    items = {e["id"]: e for e in (await me.get("/api/exercises")).json()}
    assert items["leg_press"]["preference"] == "none"


async def test_unknown_exercise_and_bad_preference(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    assert (await me.get("/api/exercises/moonwalk")).status_code == 404
    assert (
        await me.put("/api/exercises/moonwalk/preference", json={"preference": "favorite"})
    ).status_code == 404
    assert (
        await me.put("/api/exercises/push_up/preference", json={"preference": "love"})
    ).status_code == 422


async def test_preference_requires_csrf(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    del me.headers["X-CSRF-Token"]
    resp = await me.put("/api/exercises/push_up/preference", json={"preference": "favorite"})
    assert resp.status_code == 403


async def test_preferences_are_private_to_each_user(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await alice.put("/api/exercises/push_up/preference", json={"preference": "hidden"})
    await alice.put("/api/exercises/dip/preference", json={"preference": "favorite"})

    bob_items = {e["id"]: e for e in (await bob.get("/api/exercises")).json()}
    assert bob_items["push_up"]["preference"] == "none"
    assert bob_items["dip"]["preference"] == "none"

    # Bob changing the same exercise doesn't touch Alice's choice.
    await bob.put("/api/exercises/push_up/preference", json={"preference": "favorite"})
    alice_items = {e["id"]: e for e in (await alice.get("/api/exercises")).json()}
    assert alice_items["push_up"]["preference"] == "hidden"
