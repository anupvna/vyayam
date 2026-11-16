"""The coach end to end: engine-only answers, provider fallbacks, every check, actions."""

import json
import uuid
from datetime import date

import pytest
from fastapi import FastAPI

from app.coach.providers import ProviderError, Scripted
from app.config import get_settings
from tests.conftest import UserFactory

MONDAY, WEDNESDAY = "2026-11-16", "2026-11-18"  # upper/lower on Mon, Tue, Thu, Fri
PROFILE = {
    "birth_year": date.today().year - 30,
    "sex": "female",
    "height_cm": 168,
    "weight_kg": 70,
    "experience": "intermediate",
    "goal": "muscle_gain",
    "training_days": [0, 1, 3, 4],
    "session_minutes": 60,
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


async def _ready(client) -> None:
    assert (await client.put("/api/profile", json=PROFILE)).status_code == 200
    await client.post("/api/gyms", json={"name": "Gym", "equipment": GYM})
    r = await client.put("/api/plan/split", json={"split_id": "upper_lower", "today": MONDAY})
    assert r.status_code == 200, r.text


async def _ask(client, text: str, today: str = MONDAY) -> dict:
    r = await client.post("/api/coach/messages", json={"text": text, "today": today})
    assert r.status_code == 200, r.text
    user, coach = r.json()
    assert user["role"] == "user" and user["text"] == text
    return coach


def _reply(text: str, *actions: dict) -> str:
    full = [
        {"type": None, "session_key": None, "minutes": None, "exercise_id": None} | a
        for a in actions
    ]
    return json.dumps({"reply": text, "actions": full})


# ---------------------------------------------------------------- engine-only (no AI keys)


async def test_status_says_engine_only_without_keys(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    assert (await c.get("/api/coach/status")).json() == {"ai": False}


async def test_shorten_today_end_to_end(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "I only have 30 minutes today")
    assert coach["source"] == "engine"
    assert [(a["type"], a["label"]) for a in coach["actions"]] == [
        ("shorten_today", "Shorten today to 30 minutes")
    ]
    url = f"/api/coach/messages/{coach['id']}/actions/0"
    r = await c.post(url, json={"today": MONDAY})
    assert r.status_code == 200 and r.json()["minutes"] == 30
    assert (await c.post(url, json={"today": MONDAY})).status_code == 409  # only once
    history = (await c.get("/api/coach/messages")).json()
    assert history[-1]["actions"][0]["applied"] is True


async def test_skip_then_undo(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "I can't make it to the gym today")
    assert coach["actions"][0]["type"] == "skip_today"
    assert (
        await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    ).status_code == 200
    week = (await c.get(f"/api/plan/week?today={MONDAY}")).json()
    assert week["days"][0]["status"] == "skipped"

    coach = await _ask(c, "undo that please")
    assert coach["actions"][0]["type"] == "restore_today"
    await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    week = (await c.get(f"/api/plan/week?today={MONDAY}")).json()
    assert week["days"][0]["status"] == "planned"


async def test_swap_to_legs(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "can I do legs today instead?")
    assert coach["actions"][0]["type"] == "swap_today"
    assert "Lower" in coach["actions"][0]["label"]
    await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    today = (await c.get(f"/api/training/today?today={MONDAY}")).json()
    assert "Lower" in today["day"]["session_name"]


async def test_swap_without_naming_a_session(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "can I do something else today instead?")
    assert coach["actions"][0]["type"] == "swap_today"


async def test_train_at_home_today_and_back(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "I don't want to go to the gym today, can I work out at home on my mat?")
    assert [a["type"] for a in coach["actions"]] == ["train_at_home_today"]
    r = await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    assert r.status_code == 200
    assert (await c.get(f"/api/plan/today?today={MONDAY}")).json()["place"] == "home (mat only)"
    coach = await _ask(c, "going to the gym after all, back to the gym please")
    assert coach["actions"][0]["type"] == "back_to_gym_today"
    await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    assert (await c.get(f"/api/plan/today?today={MONDAY}")).json()["place"] is None


async def test_cardio_question_uses_the_log(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    body = {"id": str(uuid.uuid4()), "day": MONDAY, "activity": "treadmill", "minutes": 20}
    await c.post("/api/activities", json=body)
    coach = await _ask(c, "how much cardio have I done this week?")
    assert "20 of 75 minutes" in coach["text"]


async def test_replace_an_exercise_hides_it(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "I hate barbell rows, can you replace them?")
    assert coach["actions"][0]["type"] == "hide_exercise"
    assert "Barbell row" in coach["actions"][0]["label"]
    await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    ex = (await c.get("/api/exercises/barbell_row")).json()
    assert ex["preference"] == "hidden"


async def test_rest_day_refuses_to_skip(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "skip today", today=WEDNESDAY)
    assert coach["actions"] == []
    assert "rest day" in coach["text"]


async def test_explains_targets_from_the_engine(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "why these weights today?")
    today = (await c.get(f"/api/training/today?today={MONDAY}")).json()
    first_reason = today["exercises"][0]["target"]["reason"]
    assert first_reason in coach["text"]


async def test_apply_checks_again(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "skip today")
    today = (await c.get(f"/api/training/today?today={MONDAY}")).json()
    ex = today["exercises"][0]["exercise_id"]
    await c.post(
        "/api/logs",
        json={
            "id": str(uuid.uuid4()),
            "day": MONDAY,
            "exercise_id": ex,
            "set_index": 1,
            "weight_kg": 40,
            "reps": 8,
        },
    )
    r = await c.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    assert r.status_code == 409 and "already logged" in r.json()["detail"]


async def test_safety_needs_no_profile_and_no_ai(app: FastAPI, make_user: UserFactory) -> None:
    ai = Scripted([_reply("should never be used")], name="groq")
    app.state.coach_providers = [ai]
    c = await make_user("a@example.com")  # no profile at all
    coach = await _ask(c, "I have chest pain when I bench")
    assert coach["source"] == "safety" and "911" in coach["text"]
    assert ai.calls == []


# ---------------------------------------------------------------- with AI providers


async def test_ai_reply_with_checked_actions(app: FastAPI, make_user: UserFactory) -> None:
    ai = Scripted(
        [
            _reply(
                "Sure, tap below to fit today into 45 minutes.",
                {"type": "shorten_today", "minutes": 45},
                {"type": "swap_today", "session_key": "made_up"},  # invalid: dropped
                {"type": "hide_exercise", "exercise_id": "not_an_exercise"},  # invalid: dropped
            )
        ],
        name="groq",
    )
    app.state.coach_providers = [ai]
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "short on time")
    assert coach["source"] == "groq"
    assert [a["type"] for a in coach["actions"]] == ["shorten_today"]


async def test_the_ai_sees_data_but_not_identity(app: FastAPI, make_user: UserFactory) -> None:
    ai = Scripted([_reply("Hi"), _reply("Hi again")], name="groq")
    app.state.coach_providers = [ai]
    c = await make_user("secret.person@example.com")
    await _ready(c)
    await _ask(c, "hello coach")
    await _ask(c, "what about tomorrow?")
    sent = " ".join(t.text for t in ai.calls[1])
    assert "CONTEXT" in sent and "today_plan" in sent
    assert "secret.person" not in sent
    assert "hello coach" in sent  # remembers the conversation
    roles = [t.role for t in ai.calls[1]]
    assert all(a != b for a, b in zip(roles, roles[1:], strict=False))  # strictly alternating


async def test_bad_json_gets_one_retry(app: FastAPI, make_user: UserFactory) -> None:
    ai = Scripted(["not json at all", _reply("Fixed.")], name="groq")
    app.state.coach_providers = [ai]
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "hello")
    assert coach["text"] == "Fixed." and len(ai.calls) == 2
    assert "rejected" in ai.calls[1][-1].text


async def test_invented_numbers_move_to_the_backup(app: FastAPI, make_user: UserFactory) -> None:
    groq = Scripted([_reply("Go for 140 kg today!"), _reply("Really, 140 kg.")], name="groq")
    gemini = Scripted([_reply("Stick with today's targets.")], name="gemini")
    app.state.coach_providers = [groq, gemini]
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "how heavy should I squat?")
    assert coach["source"] == "gemini" and coach["text"] == "Stick with today's targets."


async def test_unsafe_ai_reply_never_shown(app: FastAPI, make_user: UserFactory) -> None:
    bad = _reply("Eat 900 calories a day to speed it up.")
    app.state.coach_providers = [Scripted([bad, bad], name="groq")]
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "how do I lose fat faster?")
    assert coach["source"] == "engine" and "900" not in coach["text"]


async def test_engine_answers_when_every_provider_fails(
    app: FastAPI, make_user: UserFactory
) -> None:
    app.state.coach_providers = [
        Scripted([ProviderError("groq: HTTP 429")], name="groq"),
        Scripted([ProviderError("gemini: timeout")], name="gemini"),
    ]
    c = await make_user("a@example.com")
    await _ready(c)
    coach = await _ask(c, "I only have 45 minutes")
    assert coach["source"] == "engine"
    assert coach["actions"][0]["label"] == "Shorten today to 45 minutes"


# ---------------------------------------------------------------- limits and privacy


async def test_rate_limit(make_user: UserFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "coach_messages_per_10_min", 2)
    c = await make_user("a@example.com")
    await _ready(c)
    await _ask(c, "hi")
    await _ask(c, "hi")
    r = await c.post("/api/coach/messages", json={"text": "hi", "today": MONDAY})
    assert r.status_code == 429


async def test_clear_and_isolation(make_user: UserFactory) -> None:
    a = await make_user("a@example.com")
    b = await make_user("b@example.com")
    await _ready(a)
    coach = await _ask(a, "skip today")
    r = await b.post(f"/api/coach/messages/{coach['id']}/actions/0", json={"today": MONDAY})
    assert r.status_code == 404
    assert (await b.get("/api/coach/messages")).json() == []
    assert (await a.delete("/api/coach/messages")).status_code == 204
    assert (await a.get("/api/coach/messages")).json() == []


async def test_empty_and_long_messages_rejected(make_user: UserFactory) -> None:
    c = await make_user("a@example.com")
    for text in ["   ", "x" * 1001]:
        r = await c.post("/api/coach/messages", json={"text": text, "today": MONDAY})
        assert r.status_code == 422
