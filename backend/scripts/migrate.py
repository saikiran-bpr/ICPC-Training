#!/usr/bin/env python3
"""
Apply pending SQL migrations to the Postgres database pointed to by
`DATABASE_URL`.

Migrations live in `backend/migrations/*.sql` and are applied in lexicographic
order.  Applied versions are tracked in a `schema_migrations` table.  Each
migration runs in its own transaction so a partial failure leaves the DB in
the state of the previous successful migration.

Usage:

    python -m backend.scripts.migrate          # apply pending
    python -m backend.scripts.migrate --check  # show status (no DDL)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

# Allow running both as `python -m backend.scripts.migrate` and as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.config import settings  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


def _list_migrations() -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        sys.exit(f"No migrations found in {MIGRATIONS_DIR}")
    return files


async def _applied_versions(conn: psycopg.AsyncConnection) -> set[str]:
    cur = await conn.execute("SELECT version FROM schema_migrations")
    rows = await cur.fetchall()
    return {r["version"] for r in rows}


async def cmd_apply() -> None:
    files = _list_migrations()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row, prepare_threshold=None
    ) as conn:
        # Tracking table — its own transaction.
        await conn.execute(CREATE_TRACKING_TABLE)
        await conn.commit()

        applied = await _applied_versions(conn)

        pending = [f for f in files if f.stem not in applied]
        if not pending:
            print(f"[migrate] up to date ({len(applied)} applied, 0 pending)")
            return

        for path in pending:
            sql = path.read_text(encoding="utf-8")
            print(f"[migrate] applying {path.name} ({len(sql):,} bytes)…")
            try:
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (path.stem,),
                    )
                print(f"[migrate] ✓ {path.name}")
            except Exception as e:
                print(f"[migrate] ✗ {path.name}: {e}")
                raise
        print(f"[migrate] done — {len(pending)} new migration(s) applied")


async def cmd_check() -> None:
    files = _list_migrations()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row, prepare_threshold=None
    ) as conn:
        try:
            applied = await _applied_versions(conn)
        except psycopg.errors.UndefinedTable:
            applied = set()

        print(f"Database: {settings.database_url.split('@')[1].split('/')[0]}")
        print(f"Migrations dir: {MIGRATIONS_DIR}")
        print()
        print(f"{'Version':<40} {'Status'}")
        print(f"{'-'*40} {'-'*8}")
        for f in files:
            mark = "✓ applied" if f.stem in applied else "  pending"
            print(f"{f.stem:<40} {mark}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Show status, don't apply.")
    args = ap.parse_args()
    asyncio.run(cmd_check() if args.check else cmd_apply())


if __name__ == "__main__":
    main()
