"""Shared test fixtures.

Tests run against a real Postgres (the `vyayam_test` database), not mocks, so SQL is
tested for real. Each test starts from an empty schema.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import asyncpg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.migrate import migrate

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://vyayam:vyayam@localhost:5433/vyayam_test"
)
TEST_PASSWORD = "correct horse battery"


@pytest.fixture
async def db_conn() -> AsyncIterator[asyncpg.Connection]:
    """A connection to a freshly wiped test database (no tables)."""
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def pool(db_conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Pool]:
    """A pool on a fully migrated test database."""
    await migrate(db_conn)
    p = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    try:
        yield p
    finally:
        await p.close()


@pytest.fixture
def app(pool: asyncpg.Pool) -> FastAPI:
    a = create_app(use_lifespan=False, frontend_dist=Path("/nonexistent"))
    a.state.pool = pool
    return a


UserFactory = Callable[[str], Awaitable[AsyncClient]]


@pytest.fixture
async def make_user(app: FastAPI) -> AsyncIterator[UserFactory]:
    """Sign up a user and return their logged-in client (CSRF header pre-set).

    Use two of these to prove one user can't see another's data.
    """
    clients: list[AsyncClient] = []

    async def _make(email: str) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="https://test")
        clients.append(c)
        resp = await c.post("/api/auth/signup", json={"email": email, "password": TEST_PASSWORD})
        assert resp.status_code == 201, resp.text
        c.headers["X-CSRF-Token"] = resp.json()["csrf_token"]
        return c

    yield _make
    for c in clients:
        await c.aclose()
