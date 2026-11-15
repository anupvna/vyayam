from datetime import date

import pytest

from tests.conftest import UserFactory

THIS_YEAR = date.today().year

VALID = {
    "birth_year": THIS_YEAR - 24,
    "sex": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "experience": "intermediate",
    "goal": "fat_loss",
    "target_weight_kg": 72,
    "target_body_fat_pct": 12,
    "training_days": [4, 0, 2, 3],
    "session_minutes": 60,
    "injury_areas": ["knee", "shoulder", "knee"],
    "injury_notes": "  old ACL repair  ",
    "unit_system": "imperial",
}


async def test_no_profile_until_onboarded(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    assert (await me.get("/api/profile")).status_code == 404


async def test_save_and_read_profile(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    saved = await me.put("/api/profile", json=VALID)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["training_days"] == [0, 2, 3, 4]  # sorted
    assert body["injury_areas"] == ["knee", "shoulder"]  # de-duplicated
    assert body["injury_notes"] == "old ACL repair"  # trimmed
    assert body["age"] == 24
    assert body["bmi"] == 25.2
    assert any(a["code"] == "timeline" for a in body["advice"])

    assert (await me.get("/api/profile")).json() == body


async def test_saving_again_updates(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=VALID)
    resp = await me.put("/api/profile", json=VALID | {"goal": "strength", "session_minutes": 45})
    assert resp.json()["goal"] == "strength"
    assert resp.json()["session_minutes"] == 45


async def test_unsafe_goal_is_saved_with_a_warning(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    body = (await me.put("/api/profile", json=VALID | {"target_body_fat_pct": 5})).json()
    warnings = [a for a in body["advice"] if a["level"] == "warning"]
    assert [w["code"] for w in warnings] == ["body_fat_too_low"]


@pytest.mark.parametrize(
    "change",
    [
        {"birth_year": THIS_YEAR - 15},  # under 18
        {"birth_year": THIS_YEAR - 95},
        {"training_days": [0, 1, 2, 3, 4, 5, 6]},  # no rest day
        {"training_days": []},
        {"training_days": [1, 1]},
        {"training_days": [7]},
        {"height_cm": 300},
        {"weight_kg": 10},
        {"session_minutes": 5},
        {"injury_areas": ["spleen"]},
        {"goal": "get_huge"},
        {"surprise": "field"},
    ],
)
async def test_rejects_invalid_profiles(make_user: UserFactory, change: dict) -> None:
    me = await make_user("a@example.com")
    assert (await me.put("/api/profile", json=VALID | change)).status_code == 422


async def test_saving_requires_csrf_token(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    del me.headers["X-CSRF-Token"]
    assert (await me.put("/api/profile", json=VALID)).status_code == 403


async def test_assess_previews_without_saving(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    goal = {k: VALID[k] for k in ("sex", "height_cm", "weight_kg", "goal")}
    resp = await me.post("/api/profile/assess", json=goal | {"target_weight_kg": 50})
    assert resp.status_code == 200
    assert "target_underweight" in {a["code"] for a in resp.json()}
    assert (await me.get("/api/profile")).status_code == 404


# --- isolation ------------------------------------------------------------------


async def test_users_only_ever_see_their_own_profile(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await alice.put("/api/profile", json=VALID)

    assert (await bob.get("/api/profile")).status_code == 404  # Bob sees nothing of Alice's

    await bob.put("/api/profile", json=VALID | {"goal": "strength", "sex": "female"})
    assert (await alice.get("/api/profile")).json()["goal"] == "fat_loss"  # Alice untouched
    assert (await bob.get("/api/profile")).json()["goal"] == "strength"
