"""FastAPI application entry point.

`create_app()` is a factory so tests can build an app with their own database pool
instead of the real one. The lifespan opens the pool on startup and closes it on
shutdown.

Run locally:  uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.config import get_settings
from app.db import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.pool = await create_pool(get_settings().database_url)
    try:
        yield
    finally:
        await app.state.pool.close()


def create_app(*, use_lifespan: bool = True) -> FastAPI:
    app = FastAPI(title="Vyayam", lifespan=lifespan if use_lifespan else None)
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()
