#!/usr/bin/env python3
"""
One-off import: load "Exported Problems Database.csv" into the problems table
as admin-created (created_by=32) bank problems.

Drops columns the current schema no longer has (contest_name, contest_year,
problem_index) and the per-row assignment ids (assignments live in junction
tables).  Duplicate URLs are skipped via ON CONFLICT (url) DO NOTHING.
"""
from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.config import settings  # noqa: E402

CSV_PATH = Path.home() / "Downloads" / "Exported Problems Database.csv"
ADMIN_ID = 32

COLS = [
    "name", "url", "platform", "contest_type", "rating", "difficulty", "topic",
    "sub_topic", "tags", "importance", "suggested_role", "prerequisites",
    "key_idea", "editorial_url", "time_limit_ms", "memory_limit_mb", "status",
    "assigned_to", "created_by", "is_bank", "from_contest", "notes",
    "date_added", "date_updated",
]


def clean(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    if s == "" or s.lower() == "null":
        return None
    return s


def cint(v: str | None) -> int | None:
    s = clean(v)
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def ctags(v: str | None) -> str:
    s = clean(v)
    return s if s else "[]"


def build_row(r: dict) -> tuple:
    return (
        clean(r["name"]) or r["name"],          # NOT NULL
        clean(r["url"]) or r["url"],             # NOT NULL
        clean(r["platform"]) or "Other",         # NOT NULL
        clean(r["contest_type"]),
        cint(r["rating"]),
        clean(r["difficulty"]),
        clean(r["topic"]),
        clean(r["sub_topic"]),
        ctags(r["tags"]),
        clean(r["importance"]),
        clean(r["suggested_role"]),
        clean(r["prerequisites"]),
        clean(r["key_idea"]),
        clean(r["editorial_url"]),
        cint(r["time_limit_ms"]),
        cint(r["memory_limit_mb"]),
        clean(r["status"]) or "Todo",
        clean(r["assigned_to"]),
        ADMIN_ID,                                # created_by — always admin 32
        cint(r["is_bank"]) if cint(r["is_bank"]) is not None else 1,
        cint(r["from_contest"]) if cint(r["from_contest"]) is not None else 0,
        clean(r["notes"]),
        clean(r["date_added"]),
        clean(r["date_updated"]),
    )


async def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(f"CSV not found: {CSV_PATH}")

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = [build_row(r) for r in csv.DictReader(f)]
    print(f"[import] parsed {len(rows)} rows from CSV")

    placeholders = ", ".join(["%s"] * len(COLS))
    sql = (
        f"INSERT INTO problems ({', '.join(COLS)}) VALUES ({placeholders}) "
        f"ON CONFLICT (url) DO NOTHING"
    )

    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row, prepare_threshold=None
    ) as conn:
        before = (await (await conn.execute("SELECT count(*) n FROM problems")).fetchone())["n"]
        async with conn.transaction():
            cur = conn.cursor()
            await cur.executemany(sql, rows)
        after = (await (await conn.execute("SELECT count(*) n FROM problems")).fetchone())["n"]
        admin_n = (await (await conn.execute(
            "SELECT count(*) n FROM problems WHERE created_by = %s", (ADMIN_ID,)
        )).fetchone())["n"]

    inserted = after - before
    print(f"[import] inserted {inserted} (skipped {len(rows) - inserted} dupes)")
    print(f"[import] total problems now {after}; created_by={ADMIN_ID}: {admin_n}")


if __name__ == "__main__":
    asyncio.run(main())
