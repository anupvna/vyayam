from datetime import date, timedelta

from tests.conftest import UserFactory

TODAY = date(2026, 11, 16)
PROFILE = {
    "birth_year": date.today().year - 24,
    "sex": "male",
    "height_cm": 180,
    "weight_kg": 85,
    "experience": "intermediate",
    "goal": "fat_loss",
    "target_weight_kg": 80,
    "target_body_fat_pct": 14,
    "training_days": [0, 2, 4],
    "session_minutes": 60,
}


async def test_summary_needs_a_profile(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    assert (await me.get(f"/api/body/summary?today={TODAY}")).status_code == 404


async def test_empty_summary_uses_profile_weight(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    s = (await me.get(f"/api/body/summary?today={TODAY}")).json()
    assert s["weights"] == [] and s["trend_kg"] is None
    assert s["bmi"] == 26.2 and "muscle" in s["bmi_note"]
    assert s["weight_projection"]["status"] == "not_enough_data"


async def test_weigh_ins_give_trend_rate_and_projection(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    for i in range(28):  # losing 0.08 kg a day, with a daily wobble
        day = TODAY - timedelta(days=27 - i)
        w = 85 - 0.08 * i + (0.4 if i % 3 == 0 else -0.2)
        assert (
            await me.put(f"/api/body/weights/{day}", json={"weight_kg": round(w, 1)})
        ).status_code == 204
    s = (await me.get(f"/api/body/summary?today={TODAY}")).json()
    assert len(s["weights"]) == 28
    assert -0.7 < s["rate_kg_per_week"] < -0.35
    p = s["weight_projection"]
    assert p["status"] == "on_track" and p["earliest"] < p["latest"]
    assert s["advice"] == []  # about 0.6% a week: a sensible pace
    profile = (await me.get("/api/profile")).json()
    assert profile["weight_kg"] == s["latest_weight_kg"]  # profile follows the latest weigh-in


async def test_too_fast_loss_gets_a_warning(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    for i in range(21):
        day = TODAY - timedelta(days=20 - i)
        await me.put(f"/api/body/weights/{day}", json={"weight_kg": round(85 - 0.25 * i, 2)})
    s = (await me.get(f"/api/body/summary?today={TODAY}")).json()
    assert s["advice"] and "1%" in s["advice"][0]


async def test_same_day_replaces_and_delete_works(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    await me.put(f"/api/body/weights/{TODAY}", json={"weight_kg": 84})
    await me.put(f"/api/body/weights/{TODAY}", json={"weight_kg": 83.6})
    s = (await me.get(f"/api/body/summary?today={TODAY}")).json()
    assert [w["weight_kg"] for w in s["weights"]] == [83.6]
    await me.delete(f"/api/body/weights/{TODAY}")
    assert (await me.get(f"/api/body/summary?today={TODAY}")).json()["weights"] == []


async def test_measurements_give_navy_estimate_and_manual_readings(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    week_ago = TODAY - timedelta(days=7)
    await me.put(f"/api/body/measurements/{week_ago}", json={"neck_cm": 40, "waist_cm": 90})
    await me.put(
        f"/api/body/measurements/{TODAY}", json={"body_fat_pct": 17.5, "body_fat_source": "scale"}
    )
    s = (await me.get(f"/api/body/summary?today={TODAY}")).json()
    assert s["body_fat"] == [
        {"day": str(week_ago), "pct": 18.4, "method": "navy estimate"},
        {"day": str(TODAY), "pct": 17.5, "method": "scale"},
    ]
    assert len(s["measurements"]) == 2
    assert s["body_fat_projection"]["target"] == 14


async def test_bad_body_input(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    assert (await me.put(f"/api/body/weights/{TODAY}", json={"weight_kg": 5})).status_code == 422
    assert (await me.put(f"/api/body/measurements/{TODAY}", json={})).status_code == 422
    assert (
        await me.put(f"/api/body/measurements/{TODAY}", json={"waist_cm": 500})
    ).status_code == 422


async def test_body_data_is_private(make_user: UserFactory) -> None:
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    await alice.put("/api/profile", json=PROFILE)
    await bob.put("/api/profile", json=PROFILE)
    await alice.put(f"/api/body/weights/{TODAY}", json={"weight_kg": 84})
    await alice.put(f"/api/body/measurements/{TODAY}", json={"waist_cm": 90, "neck_cm": 40})
    s = (await bob.get(f"/api/body/summary?today={TODAY}")).json()
    assert s["weights"] == [] and s["measurements"] == []
    await bob.delete(f"/api/body/weights/{TODAY}")  # can't touch Alice's
    assert len((await alice.get(f"/api/body/summary?today={TODAY}")).json()["weights"]) == 1


async def test_body_writes_need_csrf(make_user: UserFactory) -> None:
    me = await make_user("a@example.com")
    await me.put("/api/profile", json=PROFILE)
    del me.headers["X-CSRF-Token"]
    assert (await me.put(f"/api/body/weights/{TODAY}", json={"weight_kg": 84})).status_code == 403
