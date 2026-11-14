"""FastAPI dependencies shared by every endpoint.

- get_conn: borrow a DB connection for the request (FastAPI reuses it within one request).
- current_user: the logged-in user, or 401. Every user-data query filters by its `id`.
- csrf_user: current_user + CSRF check. Use it on every endpoint that changes data.

CSRF: a malicious site can make your browser send a POST with your cookie, but it
cannot read your CSRF token, so it can't set the X-CSRF-Token header. SameSite=Lax
cookies are a second layer.
"""

import hmac
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from fastapi import Depends, HTTPException, Request, status

from app.auth import sessions
from app.config import get_settings

CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str
    session_hash: str
    csrf_token: str


async def get_conn(request: Request) -> AsyncIterator[asyncpg.Connection]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


async def current_user(
    request: Request, conn: asyncpg.Connection = Depends(get_conn)
) -> CurrentUser:
    token = request.cookies.get(get_settings().session_cookie_name)
    info = await sessions.lookup(conn, token) if token else None
    if info is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return CurrentUser(
        id=info.user_id, email=info.email, session_hash=info.token_hash, csrf_token=info.csrf_token
    )


async def csrf_user(request: Request, user: CurrentUser = Depends(current_user)) -> CurrentUser:
    sent = request.headers.get(CSRF_HEADER, "")
    # compare_digest takes constant time, so timing can't leak the token byte by byte.
    if not hmac.compare_digest(sent.encode(), user.csrf_token.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    return user
