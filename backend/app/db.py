"""Database connection pool.

One asyncpg pool per process. Request handlers borrow a connection with
`async with pool.acquire() as conn:` and return it automatically.
"""

import asyncpg


async def create_pool(database_url: str) -> asyncpg.Pool:
    # Small pool: Neon's free tier limits connections, and one user doesn't need more.
    return await asyncpg.create_pool(database_url, min_size=1, max_size=5)
