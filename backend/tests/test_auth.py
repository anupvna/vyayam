from collections.abc import AsyncIterator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.sessions import hash_token
from app.main import create_app

PASSWORD = "correct horse battery"
COOKIE = "vy_session"


@pytest.fixture
def app(pool: asyncpg.Pool):
    a = create_app(use_lifespan=False)
    a.state.pool = pool
    return a


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    # https so the Secure cookie is sent back, like a real browser on HTTPS.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c


def _new_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")


async def _signup(client: AsyncClient, email: str = "anoop@example.com") -> dict:
    resp = await client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- signup ---------------------------------------------------------------


async def test_signup_logs_in_with_secure_cookie(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup", json={"email": "Anoop@Example.com", "password": PASSWORD}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "anoop@example.com"  # normalized
    assert body["csrf_token"]

    cookie = resp.headers["set-cookie"]
    assert f"{COOKIE}=" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "anoop@example.com"


async def test_password_and_token_are_never_stored_raw(
    client: AsyncClient, pool: asyncpg.Pool
) -> None:
    await _signup(client)
    token = client.cookies[COOKIE]
    async with pool.acquire() as conn:
        pw_hash = await conn.fetchval("SELECT password_hash FROM users")
        stored = await conn.fetchval("SELECT token_hash FROM sessions")
    assert pw_hash.startswith("$argon2id$") and PASSWORD not in pw_hash
    assert stored == hash_token(token) and stored != token


async def test_duplicate_email_is_case_insensitive(client: AsyncClient) -> None:
    await _signup(client, "anoop@example.com")
    resp = await client.post(
        "/api/auth/signup", json={"email": "ANOOP@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@example.com", "password": "short"},
        {"email": "a@example.com", "password": "x" * 129},
    ],
)
async def test_signup_validates_input(client: AsyncClient, payload: dict) -> None:
    resp = await client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 422


# --- login ----------------------------------------------------------------


async def test_login_success_creates_new_session(app) -> None:
    async with _new_client(app) as c1:
        await _signup(c1)
    async with _new_client(app) as c2:
        resp = await c2.post(
            "/api/auth/login", json={"email": "anoop@example.com", "password": PASSWORD}
        )
        assert resp.status_code == 200
        assert (await c2.get("/api/auth/me")).status_code == 200


async def test_login_errors_do_not_reveal_which_emails_exist(client: AsyncClient) -> None:
    await _signup(client)
    wrong_pw = await client.post(
        "/api/auth/login", json={"email": "anoop@example.com", "password": "wrong password"}
    )
    no_user = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


async def test_login_rate_limited_after_repeated_failures(client: AsyncClient) -> None:
    await _signup(client)
    bad = {"email": "anoop@example.com", "password": "wrong password"}
    for _ in range(5):
        assert (await client.post("/api/auth/login", json=bad)).status_code == 401

    # Even the correct password is refused while blocked.
    good = {"email": "anoop@example.com", "password": PASSWORD}
    resp = await client.post("/api/auth/login", json=good)
    assert resp.status_code == 429
    assert int(resp.headers["retry-after"]) > 0


# --- sessions, logout, CSRF --------------------------------------------------


async def test_me_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_garbage_cookie_is_rejected(client: AsyncClient) -> None:
    client.cookies.set(COOKIE, "made-up-token")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_expired_session_is_rejected(client: AsyncClient, pool: asyncpg.Pool) -> None:
    await _signup(client)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE sessions SET expires_at = now() - interval '1 second'")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_requires_csrf_token(client: AsyncClient) -> None:
    csrf = (await _signup(client))["csrf_token"]

    assert (await client.post("/api/auth/logout")).status_code == 403
    wrong = await client.post("/api/auth/logout", headers={"X-CSRF-Token": "nope"})
    assert wrong.status_code == 403

    ok = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_csrf_token_from_another_session_is_rejected(app) -> None:
    async with _new_client(app) as a, _new_client(app) as b:
        await _signup(a, "a@example.com")
        b_csrf = (await _signup(b, "b@example.com"))["csrf_token"]
        resp = await a.post("/api/auth/logout", headers={"X-CSRF-Token": b_csrf})
        assert resp.status_code == 403


async def test_logout_only_ends_that_session(app) -> None:
    async with _new_client(app) as phone, _new_client(app) as laptop:
        csrf = (await _signup(phone))["csrf_token"]
        await laptop.post(
            "/api/auth/login", json={"email": "anoop@example.com", "password": PASSWORD}
        )
        await phone.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
        assert (await phone.get("/api/auth/me")).status_code == 401
        assert (await laptop.get("/api/auth/me")).status_code == 200


# --- isolation ----------------------------------------------------------------


async def test_each_session_sees_only_its_own_user(app) -> None:
    async with _new_client(app) as a, _new_client(app) as b:
        await _signup(a, "a@example.com")
        await _signup(b, "b@example.com")
        assert (await a.get("/api/auth/me")).json()["user"]["email"] == "a@example.com"
        assert (await b.get("/api/auth/me")).json()["user"]["email"] == "b@example.com"


# --- demo ---------------------------------------------------------------------


async def test_demo_button_needs_the_demo_account(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/demo")
    assert resp.status_code == 404


async def test_demo_button_signs_in_without_a_password(app) -> None:
    async with _new_client(app) as owner:
        await _signup(owner, "demo@vyayam.app")
    async with _new_client(app) as visitor:
        resp = await visitor.post("/api/auth/demo")
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == "demo@vyayam.app"
        assert "HttpOnly" in resp.headers["set-cookie"]
        assert (await visitor.get("/api/auth/me")).json()["user"]["email"] == "demo@vyayam.app"


async def test_demo_button_never_opens_another_account(app) -> None:
    async with _new_client(app) as real:
        await _signup(real, "anoop@example.com")
    async with _new_client(app) as visitor:
        assert (await visitor.post("/api/auth/demo")).status_code == 404


async def test_many_demo_visitors_are_not_rate_limited(app) -> None:
    async with _new_client(app) as owner:
        await _signup(owner, "demo@vyayam.app")
    for _ in range(15):  # far past the failed-login limits
        async with _new_client(app) as visitor:
            assert (await visitor.post("/api/auth/demo")).status_code == 200
