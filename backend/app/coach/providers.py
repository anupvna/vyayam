"""AI providers behind one small interface: send a system prompt and a conversation,
get back the raw text (which should be the JSON reply).

Groq is the main provider (fast, free tier). Gemini is the backup. Both are called over
plain HTTPS with httpx; no vendor SDKs. A provider raises ProviderError on anything
that means "try the next one": no key, timeout, rate limit, server error, bad response.
"""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

log = logging.getLogger(__name__)

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


class ProviderError(Exception):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after  # seconds, when the provider says "rate limited"


class Provider(Protocol):
    name: str

    async def complete(self, system: str, turns: list[Turn], schema: dict) -> str: ...


def _fail(provider: str, res: httpx.Response) -> ProviderError:
    # Log the status only: never the request (it holds the user's data) or the key.
    log.warning("%s returned HTTP %s", provider, res.status_code)
    retry_after = None
    if res.status_code in (429, 503):  # rate limited, or the model is overloaded
        try:
            retry_after = float(res.headers.get("retry-after", ""))
        except ValueError:
            retry_after = 10.0 if res.status_code == 429 else 5.0
    return ProviderError(f"{provider}: HTTP {res.status_code}", retry_after)


class Groq:
    """OpenAI-compatible chat completions. GPT-OSS models support strict JSON schemas;
    others fall back to JSON mode (valid JSON, schema checked by us)."""

    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    strict_models = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key, self.model, self.timeout, self.transport = api_key, model, timeout, transport

    async def complete(self, system: str, turns: list[Turn], schema: dict) -> str:
        if not self.api_key:
            raise ProviderError("groq: no API key")
        fmt = (
            {
                "type": "json_schema",
                "json_schema": {"name": "coach_reply", "strict": True, "schema": schema},
            }
            if self.model in self.strict_models
            else {"type": "json_object"}
        )
        body: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}]
            + [{"role": t.role, "content": t.text} for t in turns],
            "temperature": 0.3,
            "max_completion_tokens": 1024,
            "response_format": fmt,
        }
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # enough for chat; keeps under free-tier token limits
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                res = await client.post(
                    self.url, json=body, headers={"Authorization": f"Bearer {self.api_key}"}
                )
        except httpx.HTTPError as e:
            raise ProviderError(f"groq: {type(e).__name__}") from e
        if res.status_code != 200:
            raise _fail("groq", res)
        try:
            return res.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise ProviderError("groq: unexpected response shape") from e


class Gemini:
    """Gemini generateContent with JSON output. The schema is in the prompt and checked
    by us after, which works the same across Gemini model versions."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key, self.model, self.timeout, self.transport = api_key, model, timeout, transport

    async def complete(self, system: str, turns: list[Turn], schema: dict) -> str:
        if not self.api_key:
            raise ProviderError("gemini: no API key")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if t.role == "assistant" else "user", "parts": [{"text": t.text}]}
                for t in turns
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                res = await client.post(url, json=body, headers={"x-goog-api-key": self.api_key})
        except httpx.HTTPError as e:
            raise ProviderError(f"gemini: {type(e).__name__}") from e
        if res.status_code != 200:
            raise _fail("gemini", res)
        try:
            parts = res.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise ProviderError("gemini: unexpected response shape (blocked or empty)") from e


class Scripted:
    """Replies from a list, for tests and the evaluation's offline mode. An Exception in
    the list is raised instead of returned."""

    def __init__(self, replies: list[str | Exception], name: str = "scripted") -> None:
        self.replies = list(replies)
        self.name = name
        self.calls: list[list[Turn]] = []

    async def complete(self, system: str, turns: list[Turn], schema: dict) -> str:
        self.calls.append(turns)
        if not self.replies:
            raise ProviderError(f"{self.name}: no more replies")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
