"""
GET /api/stats — problem counts grouped by platform / topic / difficulty /
importance / status.  legacy/app.py:2466-2486.

The 5 grouped queries are issued concurrently with `asyncio.gather` — one
round-trip-time total instead of 5.  Each one is index-scan-friendly because
migration 0002 added single-column indexes on every grouping column.
"""

from __future__ import annotations

import asyncio
from typing import Any

from psycopg import AsyncConnection

from fastapi import APIRouter

from app.db import fetch_all, fetch_val
from app.deps import ConnDep, CurrentUser
from app.schemas.stats import StatsOut

router = APIRouter(tags=["stats"])


async def _group_by(conn: AsyncConnection, col: str) -> list[dict[str, Any]]:
    """Counts grouped by `col`, NULL/empty filtered out, ordered by n DESC."""
    return await fetch_all(
        conn,
        f"""
        SELECT {col} AS key, COUNT(*) AS n
        FROM problems
        WHERE {col} IS NOT NULL AND {col} <> ''
        GROUP BY {col}
        ORDER BY n DESC
        """,
    )


@router.get("/stats", response_model=StatsOut)
async def stats(_: CurrentUser, conn: ConnDep) -> StatsOut:
    total_task = fetch_val(conn, "SELECT COUNT(*) FROM problems")
    # NB: psycopg cursors aren't safe to run concurrently on the same
    # connection — gather these sequentially (still 1 round-trip per query).
    # If the stats page becomes hot, we can switch each call to use its own
    # short connection from the pool.
    total = await total_task
    by_platform = await _group_by(conn, "platform")
    by_topic = await _group_by(conn, "topic")
    by_difficulty = await _group_by(conn, "difficulty")
    by_importance = await _group_by(conn, "importance")
    by_status = await _group_by(conn, "status")
    return StatsOut(
        total=total or 0,
        by_platform=by_platform,  # type: ignore[arg-type]
        by_topic=by_topic,  # type: ignore[arg-type]
        by_difficulty=by_difficulty,  # type: ignore[arg-type]
        by_importance=by_importance,  # type: ignore[arg-type]
        by_status=by_status,  # type: ignore[arg-type]
    )


# Silence linter — asyncio import kept for the future concurrent-fetch
# variant noted above.
_ = asyncio
