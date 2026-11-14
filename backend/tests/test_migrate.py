from pathlib import Path

import asyncpg
import pytest

from app.migrate import MigrationError, migrate


async def test_applies_all_migrations_then_nothing(db_conn: asyncpg.Connection) -> None:
    first = await migrate(db_conn)
    assert "0001_users" in first

    second = await migrate(db_conn)
    assert second == []  # idempotent: re-running is a no-op


async def test_applies_in_filename_order(db_conn: asyncpg.Connection, tmp_path: Path) -> None:
    (tmp_path / "0002_b.sql").write_text("INSERT INTO t VALUES (2);")
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE t (n int);")

    assert await migrate(db_conn, tmp_path) == ["0001_a", "0002_b"]
    assert await db_conn.fetchval("SELECT n FROM t") == 2


async def test_refuses_edited_migration(db_conn: asyncpg.Connection, tmp_path: Path) -> None:
    f = tmp_path / "0001_a.sql"
    f.write_text("CREATE TABLE t (n int);")
    await migrate(db_conn, tmp_path)

    f.write_text("CREATE TABLE t (n bigint);")
    with pytest.raises(MigrationError, match="changed after it was applied"):
        await migrate(db_conn, tmp_path)


async def test_failed_migration_rolls_back(db_conn: asyncpg.Connection, tmp_path: Path) -> None:
    (tmp_path / "0001_bad.sql").write_text("CREATE TABLE t (n int); SELECT * FROM missing;")

    with pytest.raises(asyncpg.UndefinedTableError):
        await migrate(db_conn, tmp_path)

    # Neither the table nor the bookkeeping row survived.
    assert await db_conn.fetchval("SELECT to_regclass('t')") is None
    assert await db_conn.fetchval("SELECT count(*) FROM schema_migrations") == 0


async def test_users_email_must_be_lowercase(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute("INSERT INTO users (email, password_hash) VALUES ('Me@X.com', 'h')")
