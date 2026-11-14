"""Server-side sessions.

Why sessions instead of JWTs: a session can be revoked instantly (logout deletes the
row), and the cookie holds only a random token, nothing readable.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class SessionInfo:
    token_hash: str
    csrf_token: str
    user_id: UUID
    email: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create(conn: asyncpg.Connection, user_id: UUID, ttl: timedelta) -> tuple[str, str]:
    """Create a session. Returns (raw token for the cookie, csrf token)."""
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    await conn.execute(
        """
        INSERT INTO sessions (token_hash, user_id, csrf_token, expires_at)
        VALUES ($1, $2, $3, now() + $4::interval)
        """,
        hash_token(token),
        user_id,
        csrf_token,
        ttl,
    )
    return token, csrf_token


async def lookup(conn: asyncpg.Connection, token: str) -> SessionInfo | None:
    row = await conn.fetchrow(
        """
        SELECT s.token_hash, s.csrf_token, u.id AS user_id, u.email
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = $1 AND s.expires_at > now()
        """,
        hash_token(token),
    )
    return SessionInfo(**dict(row)) if row else None


async def delete(conn: asyncpg.Connection, token_hash: str) -> None:
    await conn.execute("DELETE FROM sessions WHERE token_hash = $1", token_hash)


async def purge_expired(conn: asyncpg.Connection, user_id: UUID) -> None:
    await conn.execute("DELETE FROM sessions WHERE user_id = $1 AND expires_at <= now()", user_id)
