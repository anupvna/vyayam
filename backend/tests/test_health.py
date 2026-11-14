from contextlib import asynccontextmanager

import asyncpg
from httpx import ASGITransport, AsyncClient

from app.main import create_app


def _client(pool: object) -> AsyncClient:
    app = create_app(use_lifespan=False)
    app.state.pool = pool
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health_ok(pool: asyncpg.Pool) -> None:
    async with _client(pool) as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


class _BrokenPool:
    @asynccontextmanager
    async def acquire(self):
        raise ConnectionRefusedError("database is down")
        yield  # pragma: no cover


async def test_health_reports_db_down() -> None:
    async with _client(_BrokenPool()) as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 503
    assert resp.json()["database"] == "unreachable"
