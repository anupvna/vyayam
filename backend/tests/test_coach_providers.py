"""Provider HTTP calls, checked against the documented request and response formats
(no network: httpx.MockTransport)."""

import json

import httpx
import pytest

from app.coach.providers import Gemini, Groq, ProviderError, Turn
from app.coach.service import REPLY_SCHEMA

TURNS = [Turn("user", "ctx"), Turn("assistant", "ok"), Turn("user", "hi")]


def _mock(status: int, payload: object, seen: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handle)


async def test_groq_request_and_reply() -> None:
    seen: list[httpx.Request] = []
    reply = {
        "choices": [{"message": {"role": "assistant", "content": '{"reply":"x","actions":[]}'}}]
    }
    groq = Groq("gsk_test", "openai/gpt-oss-120b", 5, transport=_mock(200, reply, seen))
    assert await groq.complete("SYS", TURNS, REPLY_SCHEMA) == '{"reply":"x","actions":[]}'

    req = seen[0]
    assert str(req.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer gsk_test"
    body = json.loads(req.content)
    assert body["model"] == "openai/gpt-oss-120b"
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert body["reasoning_effort"] == "low"


async def test_groq_other_models_use_json_mode() -> None:
    seen: list[httpx.Request] = []
    reply = {"choices": [{"message": {"content": "{}"}}]}
    groq = Groq("k", "llama-3.3-70b-versatile", 5, transport=_mock(200, reply, seen))
    await groq.complete("SYS", TURNS, REPLY_SCHEMA)
    body = json.loads(seen[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in body


@pytest.mark.parametrize(("status", "retry"), [(401, None), (429, 10.0), (500, None), (503, 5.0)])
async def test_groq_errors_mean_next_provider(status: int, retry: float | None) -> None:
    groq = Groq("k", "openai/gpt-oss-120b", 5, transport=_mock(status, {"error": {}}, []))
    with pytest.raises(ProviderError) as e:
        await groq.complete("SYS", TURNS, REPLY_SCHEMA)
    assert e.value.retry_after == retry


async def test_rate_limit_wait_comes_from_the_header() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "7"}, json={})

    groq = Groq("k", "openai/gpt-oss-120b", 5, transport=httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as e:
        await groq.complete("SYS", TURNS, REPLY_SCHEMA)
    assert e.value.retry_after == 7.0


async def test_missing_keys_mean_next_provider() -> None:
    with pytest.raises(ProviderError):
        await Groq("", "m", 5).complete("SYS", TURNS, REPLY_SCHEMA)
    with pytest.raises(ProviderError):
        await Gemini("", "m", 5).complete("SYS", TURNS, REPLY_SCHEMA)


async def test_gemini_request_and_reply_skips_thoughts() -> None:
    seen: list[httpx.Request] = []
    reply = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "thinking...", "thought": True},
                        {"text": '{"reply":"y",'},
                        {"text": '"actions":[]}'},
                    ],
                }
            }
        ]
    }
    gem = Gemini("AIza_test", "gemini-flash-latest", 5, transport=_mock(200, reply, seen))
    assert await gem.complete("SYS", TURNS, REPLY_SCHEMA) == '{"reply":"y","actions":[]}'

    req = seen[0]
    assert str(req.url).endswith("/v1beta/models/gemini-flash-latest:generateContent")
    assert req.headers["x-goog-api-key"] == "AIza_test"
    assert "key=" not in str(req.url)  # the key never goes in the URL (it would end up in logs)
    body = json.loads(req.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"


async def test_gemini_blocked_or_empty_reply() -> None:
    gem = Gemini(
        "k", "m", 5, transport=_mock(200, {"promptFeedback": {"blockReason": "SAFETY"}}, [])
    )
    with pytest.raises(ProviderError):
        await gem.complete("SYS", TURNS, REPLY_SCHEMA)


async def test_network_failure_means_next_provider() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    gem = Gemini("k", "m", 5, transport=httpx.MockTransport(boom))
    with pytest.raises(ProviderError):
        await gem.complete("SYS", TURNS, REPLY_SCHEMA)


def test_reply_schema_meets_strict_mode_rules() -> None:
    """Groq strict mode: every object lists all properties as required and forbids extras."""

    def walk(node: dict) -> None:
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        if node.get("type") == "array":
            walk(node["items"])

    walk(REPLY_SCHEMA)
