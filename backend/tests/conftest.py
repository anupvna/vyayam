"""Shared test fixtures.

Tests run against a real Postgres (the `vyayam_test` database), not mocks, so SQL is
tested for real. Each test starts from an empty schema.
"""

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest

from app.migrate import migrate

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://vyayam:vyayam@localhost:5433/vyayam_test"
)


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
