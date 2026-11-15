import uuid

from httpx import ASGITransport, AsyncClient

from app.catalog import EQUIPMENT_IDS, PRESETS
from tests.conftest import UserFactory


async def _create(client: AsyncClient, name: str, equipment: list[str] | None = None) -> dict:
    resp = await client.post("/api/gyms", json={"name": name, "equipment": equipment or []})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_catalog_is_public_and_consistent(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        body = (await c.get("/api/catalog")).json()
    ids = {e["id"] for e in body["equipment"]}
    categories = {c["id"] for c in body["categories"]}
    assert ids == EQUIPMENT_IDS
    assert all(e["category"] in categories for e in body["equipment"])
    for preset in body["presets"]:
        assert set(preset["equipment"]) <= ids  # presets only use real equipment
    assert {p["id"] for p in body["presets"]} == {p.id for p in PRESETS}


async def test_first_gym_is_active_and_later_ones_are_not(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    first = await _create(me, "NYU gym", ["barbell", "dumbbells", "barbell"])
    second = await _create(me, "  Home  ", ["dumbbells"])
    assert first["is_active"] and not second["is_active"]
    assert first["equipment"] == ["barbell", "dumbbells"]  # de-duplicated
    assert second["name"] == "Home"  # trimmed


async def test_activate_switches_the_single_active_gym(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    first = await _create(me, "NYU gym")
    second = await _create(me, "Home")

    resp = await me.post(f"/api/gyms/{second['id']}/activate")
    assert resp.status_code == 200 and resp.json()["is_active"]

    gyms = (await me.get("/api/gyms")).json()
    active = [g["id"] for g in gyms if g["is_active"]]
    assert active == [second["id"]] and first["id"] not in active


async def test_update_gym(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    gym = await _create(me, "NYU gym")
    resp = await me.put(
        f"/api/gyms/{gym['id']}", json={"name": "Dodge gym", "equipment": ["leg_press"]}
    )
    assert resp.json()["name"] == "Dodge gym"
    assert resp.json()["equipment"] == ["leg_press"]


async def test_deleting_active_gym_promotes_another(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    first = await _create(me, "NYU gym")
    second = await _create(me, "Home")
    assert (await me.delete(f"/api/gyms/{first['id']}")).status_code == 204
    gyms = (await me.get("/api/gyms")).json()
    assert [(g["id"], g["is_active"]) for g in gyms] == [(second["id"], True)]


async def test_rejects_unknown_equipment_and_blank_names(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    bad_item = await me.post("/api/gyms", json={"name": "X", "equipment": ["jetpack"]})
    blank = await me.post("/api/gyms", json={"name": "   ", "equipment": []})
    assert bad_item.status_code == 422 and blank.status_code == 422


async def test_gym_limit(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    for i in range(10):
        await _create(me, f"Gym {i}")
    assert (await me.post("/api/gyms", json={"name": "One more"})).status_code == 409


async def test_unknown_gym_is_404(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    assert (await me.post(f"/api/gyms/{uuid.uuid4()}/activate")).status_code == 404


# --- isolation ------------------------------------------------------------------


async def test_users_cannot_see_or_touch_each_others_gyms(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    gym = await _create(alice, "Alice's gym", ["barbell"])
    gym_url = f"/api/gyms/{gym['id']}"

    assert (await bob.get("/api/gyms")).json() == []
    # Every write by Bob on Alice's gym looks exactly like "not found".
    assert (await bob.put(gym_url, json={"name": "Hacked", "equipment": []})).status_code == 404
    assert (await bob.post(f"{gym_url}/activate")).status_code == 404
    assert (await bob.delete(gym_url)).status_code == 404

    # Alice's gym is unchanged, and Bob's own first gym still becomes active for him.
    assert (await alice.get("/api/gyms")).json() == [gym]
    assert (await _create(bob, "Bob's gym"))["is_active"]
    assert len((await alice.get("/api/gyms")).json()) == 1
