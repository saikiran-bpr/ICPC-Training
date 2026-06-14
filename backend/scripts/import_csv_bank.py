#!/usr/bin/env python3
"""
One-off import: load "Exported Problems Database.csv" into the problems table
as admin-created bank problems.

created_by is resolved at runtime: env CREATED_BY if set, otherwise the first
Admin user in the DB (portable across databases).  Drops columns the current
schema no longer has (contest_name, contest_year, problem_index) and the
per-row assignment ids (assignments live in junction tables).  Duplicate URLs
are skipped via ON CONFLICT (url) DO NOTHING.  Imported rows are set to
from_contest=0 so they all appear in the Problem Bank.
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.config import settings  # noqa: E402

CSV_PATH = Path.home() / "Downloads" / "Exported Problems Database.csv"
CREATED_BY_ENV = os.environ.get("CREATED_BY")

COLS = [
    "name", "url", "platform", "contest_type", "rating", "difficulty", "topic",
    "sub_topic", "tags", "importance", "key_idea", "status",
    "created_by", "from_contest", "notes", "date_added", "date_updated",
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


def build_row(r: dict, created_by: int) -> tuple:
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
        clean(r["key_idea"]),
        clean(r["status"]) or "Todo",
        created_by,
        cint(r["from_contest"]) if cint(r["from_contest"]) is not None else 0,
        clean(r["notes"]),
        clean(r["date_added"]),
        clean(r["date_updated"]),
    )


async def _resolve_created_by(conn: psycopg.AsyncConnection) -> int:
    if CREATED_BY_ENV:
        return int(CREATED_BY_ENV)
    row = await (
        await conn.execute(
            "SELECT id FROM users WHERE role = 'Admin' ORDER BY id LIMIT 1"
        )
    ).fetchone()
    if not row:
        sys.exit("No Admin user found — create one first (scripts.create_admin).")
    return row["id"]


async def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(f"CSV not found: {CSV_PATH}")

    placeholders = ", ".join(["%s"] * len(COLS))
    sql = (
        f"INSERT INTO problems ({', '.join(COLS)}) VALUES ({placeholders}) "
        f"ON CONFLICT (url) DO NOTHING"
    )

    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row, prepare_threshold=None
    ) as conn:
        created_by = await _resolve_created_by(conn)
        with CSV_PATH.open(encoding="utf-8", newline="") as f:
            rows = [build_row(r, created_by) for r in csv.DictReader(f)]
        print(f"[import] parsed {len(rows)} rows; created_by={created_by}")

        before = (await (await conn.execute("SELECT count(*) n FROM problems")).fetchone())["n"]
        async with conn.transaction():
            cur = conn.cursor()
            await cur.executemany(sql, rows)
            # Make all imported problems visible in the Problem Bank.
            await conn.execute(
                "UPDATE problems SET from_contest = 0 "
                "WHERE created_by = %s AND from_contest = 1",
                (created_by,),
            )
        after = (await (await conn.execute("SELECT count(*) n FROM problems")).fetchone())["n"]
        admin_n = (await (await conn.execute(
            "SELECT count(*) n FROM problems WHERE created_by = %s", (created_by,)
        )).fetchone())["n"]

    inserted = after - before
    print(f"[import] inserted {inserted} (skipped {len(rows) - inserted} dupes)")
    print(f"[import] total problems now {after}; created_by={created_by}: {admin_n}")


if __name__ == "__main__":
    asyncio.run(main())
