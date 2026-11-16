"""FastAPI application entry point.

`create_app()` is a factory so tests can build an app with their own database pool
instead of the real one. The lifespan opens the pool on startup and closes it on
shutdown.

Run locally:  uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import auth, body, catalog, exercises, gyms, health, plan, profile, stats, training
from app.auth.ratelimit import FailureLimiter
from app.config import get_settings
from app.db import create_pool
from app.spa import mount_spa


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.pool = await create_pool(get_settings().database_url)
    try:
        yield
    finally:
        await app.state.pool.close()


def create_app(*, use_lifespan: bool = True, frontend_dist: Path | None = None) -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Vyayam", lifespan=lifespan if use_lifespan else None)

    # Each app instance gets its own limiters, so tests never share counts.
    app.state.email_limiter = FailureLimiter(s.login_max_failures_per_email, s.login_window_seconds)
    app.state.ip_limiter = FailureLimiter(s.login_max_failures_per_ip, s.login_window_seconds)

    for module in (health, auth, catalog, profile, gyms, exercises, plan, training, body, stats):
        app.include_router(module.router, prefix="/api")

    # Registered last, so every /api route above wins over the catch-all.
    dist = frontend_dist if frontend_dist is not None else s.frontend_dist
    if (dist / "index.html").is_file():
        mount_spa(app, dist)
    return app


app = create_app()
