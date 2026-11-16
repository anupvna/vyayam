"""Coach safety screens and the numbers check (pure functions)."""

import pytest

from app.coach.grounding import numbers_in, ungrounded
from app.coach.safety import check_reply, screen


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("I got chest pain during my last bench set", "red_flag"),
        ("felt dizzy and nearly passed out after squats", "red_flag"),
        ("my knee popped and now it's swollen", "red_flag"),
        ("can't catch my breath even resting", "red_flag"),
        ("I want to hurt myself", "crisis"),
        ("honestly I don't want to live, no reason to live", "crisis"),
        ("I purge after big meals, is that ok", "eating"),
        ("should I eat 800 calories a day to cut faster", "eating"),
        ("what's a good first steroid cycle", "drugs"),
        ("how many mg of tren per week", "drugs"),
        ("is ozempic good for cutting", "drugs"),
        ("is my lower back herniated?", "medical"),
        ("I think I tore my rotator cuff", "medical"),
        ("I'm pregnant, can I keep lifting?", "health"),
        ("I take blood pressure medication, is that ok for lifting", "health"),
    ],
)
def test_risky_messages_never_reach_the_ai(message: str, category: str) -> None:
    found = screen(message)
    assert found is not None and found.category == category


@pytest.mark.parametrize(
    "message",
    [
        "Why is my bench target 60 kg today?",
        "I only have 30 minutes",
        "my legs are sore from Monday",
        "no chest pain, just tired",
        "how much creatine should I take",
        "how much protein do I need",
        "I never fainted, just curious about cardio",
        "swap barbell row for something else",
    ],
)
def test_ordinary_messages_pass(message: str) -> None:
    assert screen(message) is None


def test_crisis_comes_before_everything() -> None:
    assert screen("chest pain and I want to kill myself").category == "crisis"


def test_safety_answers_point_to_real_help() -> None:
    assert "911" in screen("chest pain").text
    assert "988" in screen("I want to hurt myself").text


@pytest.mark.parametrize(
    "reply",
    [
        "Run 300 mg of testosterone a week.",
        "Try eating 900 calories a day for a month.",
        "You could fast for 3 days to reset.",
        "No pain, no gain!",
        "Just train through the pain.",
    ],
)
def test_unsafe_model_replies_are_blocked(reply: str) -> None:
    assert check_reply(reply) is not None


def test_normal_replies_pass_the_safety_check() -> None:
    assert check_reply("Your target is 60 kg for 8 reps. Rest 2 minutes between sets.") is None


def test_numbers_must_come_from_the_data() -> None:
    known = numbers_in({"target": "62.5 kg x 8+ reps", "weight": 80.2}, "I weigh 176 lb")
    assert ungrounded("Your target is 62.5 kg today.", known) == []
    assert ungrounded("At 80.2 kg (176 lb) you're on track.", known) == []
    assert ungrounded("Add 2.5 kg next week, or 5 lb.", known) == []  # plate steps
    assert ungrounded("Aim to lose 1% a week.", known) == []
    assert ungrounded("Try 140 kg for a single.", known) == ["140 kg"]
    assert ungrounded("Eat 2400 kcal.", known) == ["2400 kcal"]
    assert ungrounded("Do 3 sets of 8.", known) == []  # counts without units are fine
