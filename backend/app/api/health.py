"""Health check: is the API up, and can it reach the database?

Render pings this to know the service is alive. It returns 503 (not 500) when the
database is unreachable, so a monitor can tell "app broken" from "DB down".
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    try:
        async with request.app.state.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
