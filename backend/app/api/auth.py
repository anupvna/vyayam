"""Account endpoints: signup, login, logout, me.

Login errors are deliberately vague ("invalid email or password") so the API doesn't
confirm which emails have accounts. Signup has to say "email taken"; that's the
usual, accepted trade-off.
"""

import asyncio
from datetime import timedelta
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.auth import sessions
from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.auth.passwords import burn_verify_time, hash_password, verify_password
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: UUID
    email: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


def _normalize(email: str) -> str:
    return email.strip().lower()


def _set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        token,
        max_age=s.session_ttl_days * 24 * 3600,
        httponly=True,  # JavaScript can't read it, so an XSS bug can't steal it
        secure=s.cookie_secure,  # only sent over HTTPS
        samesite="lax",  # not sent on cross-site POSTs
        path="/",
    )


async def _start_session(conn: asyncpg.Connection, response: Response, user_id: UUID) -> str:
    ttl = timedelta(days=get_settings().session_ttl_days)
    token, csrf_token = await sessions.create(conn, user_id, ttl)
    _set_session_cookie(response, token)
    return csrf_token


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SessionOut)
async def signup(
    body: SignupRequest, response: Response, conn: asyncpg.Connection = Depends(get_conn)
) -> SessionOut:
    email = _normalize(body.email)
    password_hash = await asyncio.to_thread(hash_password, body.password)
    try:
        user_id = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email,
            password_hash,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from None
    csrf_token = await _start_session(conn, response, user_id)
    return SessionOut(user=UserOut(id=user_id, email=email), csrf_token=csrf_token)


@router.post("/login", response_model=SessionOut)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_conn),
) -> SessionOut:
    email = _normalize(body.email)
    ip = request.client.host if request.client else "unknown"
    email_key, ip_key = f"email:{email}", f"ip:{ip}"
    email_limiter = request.app.state.email_limiter
    ip_limiter = request.app.state.ip_limiter

    wait = email_limiter.retry_after(email_key) or ip_limiter.retry_after(ip_key)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    row = await conn.fetchrow("SELECT id, password_hash FROM users WHERE email = $1", email)
    if row is None:
        await asyncio.to_thread(burn_verify_time, body.password)
        ok = False
    else:
        ok = await asyncio.to_thread(verify_password, row["password_hash"], body.password)

    if not ok:
        email_limiter.record_failure(email_key)
        ip_limiter.record_failure(ip_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    email_limiter.reset(email_key)
    await sessions.purge_expired(conn, row["id"])
    csrf_token = await _start_session(conn, response, row["id"])
    return SessionOut(user=UserOut(id=row["id"], email=email), csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: CurrentUser = Depends(csrf_user), conn: asyncpg.Connection = Depends(get_conn)
) -> Response:
    await sessions.delete(conn, user.session_hash)
    s = get_settings()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        s.session_cookie_name, path="/", secure=s.cookie_secure, httponly=True, samesite="lax"
    )
    return response


@router.get("/me", response_model=SessionOut)
async def me(user: CurrentUser = Depends(current_user)) -> SessionOut:
    # The frontend calls this on load to learn who's logged in and get the CSRF token.
    return SessionOut(user=UserOut(id=user.id, email=user.email), csrf_token=user.csrf_token)
