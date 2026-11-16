"""Logging cardio and floor work, the week's cardio, today's suggestions, and
training somewhere else for a day."""

import uuid
from datetime import date

from tests.conftest import UserFactory

MONDAY, WEDNESDAY = "2026-11-16", "2026-11-18"
PROFILE = {
    "birth_year": date.today().year - 30,
    "sex": "male",
    "height_cm": 180,
    "weight_kg": 80,
    "experience": "intermediate",
    "goal": "fat_loss",
    "training_days": [0, 2, 4],
    "session_minutes": 60,
    "injury_areas": [],
}
GYM = ["barbell", "dumbbells", "squat_rack", "flat_bench", "pull_up_bar", "lat_pulldown",
       "cable_station", "treadmill", "bike"]  # fmt: skip


async def _ready(c) -> None:
    assert (await c.put("/api/profile", json=PROFILE)).status_code == 200
    await c.post("/api/gyms", json={"name": "Iron Gym", "equipment": GYM})
    r = await c.put("/api/plan/split", json={"split_id": "full_body", "today": MONDAY})
    assert r.status_code == 200, r.text


def _act(**over) -> dict:
    return {"id": str(uuid.uuid4()), "day": MONDAY, "activity": "treadmill", "minutes": 30} | over


async def test_log_treadmill_with_speed_and_incline(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    r = await c.post("/api/activities", json=_act(speed_kmh=5, incline_pct=5, minutes=30))
    assert r.status_code == 201, r.text
    a = r.json()
    # 5.52 MET * 3.5 * 80 kg / 200 * 30 min = 232 kcal
    assert a["calories"] == 232 and a["calories_estimated"] is True
    assert a["name"] == "Treadmill"


async def test_machine_calories_win_over_the_estimate(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    a = (await c.post("/api/activities", json=_act(activity="bike", calories=210, level=8))).json()
    assert a["calories"] == 210 and a["calories_estimated"] is False


async def test_resend_is_not_a_duplicate(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    other = await make_user("b@example.com")
    await _ready(c)
    body = _act()
    assert (await c.post("/api/activities", json=body)).status_code == 201
    assert (await c.post("/api/activities", json=body)).status_code == 201
    week = (await c.get(f"/api/activities/week?today={MONDAY}")).json()
    assert len(week["activities"]) == 1
    await _ready(other)
    assert (await other.post("/api/activities", json=body)).status_code == 409


async def test_mat_workout_with_floor_moves(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    body = _act(activity="mat_workout", minutes=20, items=["crunch", "plank", "burpee", "crunch"])
    a = (await c.post("/api/activities", json=body)).json()
    assert a["items"] == ["crunch", "plank", "burpee"]
    assert a["item_names"] == ["Crunch", "Plank", "Burpees"]
    bad = _act(activity="mat_workout", items=["back_squat"])  # needs a barbell: not a floor move
    assert (await c.post("/api/activities", json=bad)).status_code == 422
    assert (await c.post("/api/activities", json=_act(activity="flying"))).status_code == 422
    assert (await c.post("/api/activities", json=_act(minutes=0))).status_code == 422


async def test_week_counts_cardio_against_the_goal_target(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    await c.post("/api/activities", json=_act(minutes=25))
    await c.post("/api/activities", json=_act(day=WEDNESDAY, activity="walk", minutes=40))
    await c.post("/api/activities", json=_act(activity="stretching", minutes=10))  # not cardio
    await c.post("/api/activities", json=_act(activity="mat_workout", minutes=15))  # nor this
    week = (await c.get(f"/api/activities/week?today={WEDNESDAY}")).json()
    assert week["level"] == "regular" and week["chosen"] is None  # fat loss -> regular
    assert week["target_minutes"] == 150 and week["done_minutes"] == 65
    assert [d["minutes"] for d in week["days"]][:3] == [25, 0, 40]

    r = await c.put(f"/api/activities/level?today={WEDNESDAY}", json={"level": "light"})
    assert r.json()["target_minutes"] == 75 and r.json()["chosen"] == "light"
    r = await c.put(f"/api/activities/level?today={WEDNESDAY}", json={"level": None})
    assert r.json()["target_minutes"] == 150


async def test_delete_only_your_own(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    other = await make_user("b@example.com")
    await _ready(c)
    a = (await c.post("/api/activities", json=_act())).json()
    await other.delete(f"/api/activities/{a['id']}")
    assert len((await c.get(f"/api/activities/week?today={MONDAY}")).json()["activities"]) == 1
    await c.delete(f"/api/activities/{a['id']}")
    assert (await c.get(f"/api/activities/week?today={MONDAY}")).json()["activities"] == []


async def test_today_suggestions(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    t = (await c.get(f"/api/activities/today?today={MONDAY}")).json()
    assert t["warmup"]["activity"] == "treadmill" and t["warmup"]["done"] is False
    assert t["finisher"] is not None  # fat loss
    assert len(t["cooldown"]) >= 2 and t["cooldown_minutes"] >= 1
    assert t["rest_day"] is None

    await c.post("/api/activities", json=_act(part="warmup", minutes=5))
    assert (await c.get(f"/api/activities/today?today={MONDAY}")).json()["warmup"]["done"] is True

    rest = (await c.get("/api/activities/today?today=2026-11-17")).json()
    assert rest["warmup"] is None and rest["cooldown"] == [] and "minutes" in rest["rest_day"]


async def test_train_at_home_on_a_mat_for_one_day(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    before = (await c.get(f"/api/plan/today?today={MONDAY}")).json()
    r = await c.put(f"/api/plan/days/{MONDAY}/place", json={"today": MONDAY, "mat": True})
    assert r.status_code == 200, r.text
    day = r.json()
    assert day["place"] == "home (mat only)"
    assert day["exercises"] and day["exercises"] != before["exercises"]
    lib = {e["id"]: e for e in (await c.get("/api/exercises")).json()}
    for e in day["exercises"]:
        assert (
            lib[e["exercise_id"]]["equipment"] == [[]] or [] in lib[e["exercise_id"]]["equipment"]
        )
    # Warm-up follows the place: no treadmill on a mat.
    t = (await c.get(f"/api/activities/today?today={MONDAY}")).json()
    assert t["warmup"]["activity"] == "hiit"
    # Only that day changes.
    friday = (await c.get("/api/plan/today?today=2026-11-20")).json()
    assert friday["place"] is None
    # Back to the gym.
    assert (await c.delete(f"/api/plan/days/{MONDAY}/place")).status_code == 204
    assert (await c.get(f"/api/plan/today?today={MONDAY}")).json() == before


async def test_another_gym_for_a_day(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    hotel = (
        await c.post("/api/gyms", json={"name": "Hotel gym", "equipment": ["dumbbells"]})
    ).json()
    gyms = (await c.get("/api/gyms")).json()
    active = next(g for g in gyms if g["is_active"])
    day = (
        await c.put(f"/api/plan/days/{MONDAY}/place", json={"today": MONDAY, "gym_id": hotel["id"]})
    ).json()
    assert day["place"] == "Hotel gym"
    # Choosing the usual gym clears the override.
    day = (
        await c.put(
            f"/api/plan/days/{MONDAY}/place", json={"today": MONDAY, "gym_id": active["id"]}
        )
    ).json()
    assert day["place"] is None


async def test_place_rules(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    both = {"today": MONDAY, "mat": True, "gym_id": str(uuid.uuid4())}
    assert (await c.put(f"/api/plan/days/{MONDAY}/place", json=both)).status_code == 422
    assert (
        await c.put(f"/api/plan/days/{MONDAY}/place", json={"today": MONDAY})
    ).status_code == 422
    past = await c.put("/api/plan/days/2026-11-10/place", json={"today": MONDAY, "mat": True})
    assert past.status_code == 409
    nope = await c.put(
        f"/api/plan/days/{MONDAY}/place", json={"today": MONDAY, "gym_id": str(uuid.uuid4())}
    )
    assert nope.status_code == 404


async def test_catalog_lists_activities_and_floor_moves(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    cat = (await c.get("/api/catalog")).json()
    assert {"treadmill", "stair_climber", "jump_rope", "mat_workout", "walk"} <= {
        a["id"] for a in cat["activities"]
    }
    groups = {m["group"] for m in cat["floor_moves"]}
    assert groups == {"core", "legs", "upper", "hiit", "stretch"}
    assert {"mat", "jump_rope", "stair_climber"} <= {e["id"] for e in cat["equipment"]}
    assert any(p["id"] == "mat" for p in cat["presets"])
