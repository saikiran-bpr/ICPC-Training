"""
Async psycopg connection pool + per-request transaction dependency.

Skill rules applied:
  • conn-pooling           — psycopg_pool.AsyncConnectionPool, min=2 max=10
  • conn-prepared-statements — prepare_threshold=None (pooler-friendly)
  • lock-short-transactions — each request gets one short tx via `tx()` dep,
                              commit on success / rollback on exception
  • conn-idle-timeout      — pool's max_idle handles this

Repositories receive an `AsyncConnection` (already inside a transaction) and
call `.execute(...)` / `.cursor()` normally.  They never create their own
connections or transactions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

# Created lazily on first use so importing app.db doesn't open a connection
# (matters for tests + CLI scripts that don't need the pool).
_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            kwargs={
                "row_factory": dict_row,
                # Disable named prepared statements so this works against the
                # Supabase transaction-mode pooler (port 6543) if we switch.
                "prepare_threshold": None,
            },
            # Liveness check: psycopg runs `SELECT 1` before handing a
            # connection out.  Cheap, and saves the first request after an
            # idle period (Supabase recycles idle conns after a few minutes)
            # from blowing up with "connection broken" — the pool replaces
            # the bad socket transparently.
            check=AsyncConnectionPool.check_connection,
            open=False,
        )
        await _pool.open(wait=True, timeout=10)
    return _pool


async def close_pool() -> None:
    """Called from the FastAPI lifespan on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Per-request transaction dependency
# ---------------------------------------------------------------------------

async def tx() -> AsyncIterator[AsyncConnection]:
    """FastAPI dependency: yield an `AsyncConnection` already inside a tx.

    Usage:

        @router.post(...)
        async def handler(conn: Annotated[AsyncConnection, Depends(tx)]):
            await conn.execute("INSERT ...")

    Commit / rollback is automatic.  Repository functions just `await
    conn.execute(...)` — they never call `.commit()` themselves.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            yield conn


# ---------------------------------------------------------------------------
# Helpers for one-off scripts (migrations, CLI seeders)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def standalone_connection() -> AsyncIterator[AsyncConnection]:
    """Open a one-shot connection without going through the pool.

    Used by migration / admin CLIs which run outside the FastAPI lifespan.
    """
    async with await AsyncConnection.connect(
        conninfo=settings.database_url,
        row_factory=dict_row,
        prepare_threshold=None,
    ) as conn:
        yield conn


# ---------------------------------------------------------------------------
# Tiny query helpers — saves typing in repositories
# ---------------------------------------------------------------------------

async def fetch_one(conn: AsyncConnection, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    cur = await conn.execute(sql, params)
    return await cur.fetchone()


async def fetch_all(conn: AsyncConnection, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    cur = await conn.execute(sql, params)
    return await cur.fetchall()


async def execute(conn: AsyncConnection, sql: str, params: tuple | list = ()) -> int:
    """Run a write statement; returns affected rowcount."""
    cur = await conn.execute(sql, params)
    return cur.rowcount


async def fetch_val(conn: AsyncConnection, sql: str, params: tuple | list = ()) -> Any:
    """Run a query expected to return one row with one column."""
    cur = await conn.execute(sql, params)
    row = await cur.fetchone()
    if row is None:
        return None
    return next(iter(row.values()))
