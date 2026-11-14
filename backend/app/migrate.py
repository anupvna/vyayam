"""Minimal SQL migration runner.

Rules:
- Migrations are plain .sql files in backend/migrations/, applied in filename order
  (0001_..., 0002_...).
- Each file runs inside its own transaction: it either fully applies or not at all.
- Applied files are recorded in `schema_migrations` with a SHA-256 checksum. If an
  already-applied file is edited later, we refuse to run: history must not change,
  so fixes go in a new migration.
- A Postgres advisory lock stops two processes from migrating at the same time.

Run it with:  python -m app.migrate
"""

import asyncio
import hashlib
from pathlib import Path

import asyncpg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_LOCK_ID = 7_438_201  # arbitrary constant shared by every runner of this app


class MigrationError(RuntimeError):
    pass


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _load(directory: Path) -> list[tuple[str, str, str]]:
    """Read migration files as (version, filename, sql), sorted by filename.

    Plain (sync) file reads happen here, before any async database work.
    """
    return [
        (p.stem, p.name, p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.sql"))
    ]


async def migrate(conn: asyncpg.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns the versions applied by this call."""
    files = _load(directory)
    await conn.execute("SELECT pg_advisory_lock($1)", _LOCK_ID)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    text PRIMARY KEY,
                checksum   text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {r["version"]: r["checksum"] for r in rows}

        newly_applied: list[str] = []
        for version, filename, sql in files:
            checksum = _checksum(sql)

            if version in applied:
                if applied[version] != checksum:
                    raise MigrationError(
                        f"{filename} changed after it was applied. "
                        "Never edit an applied migration; add a new one instead."
                    )
                continue

            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
                    version,
                    checksum,
                )
            newly_applied.append(version)
        return newly_applied
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", _LOCK_ID)


async def _main() -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        applied = await migrate(conn)
    finally:
        await conn.close()
    print("Applied:", ", ".join(applied) if applied else "nothing (already up to date)")


if __name__ == "__main__":
    asyncio.run(_main())
