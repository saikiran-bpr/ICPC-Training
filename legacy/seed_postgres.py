#!/usr/bin/env python3
"""
Apply schema.sql to the Supabase project pointed to by DATABASE_URL.

Idempotent: every CREATE in schema.sql uses IF NOT EXISTS / OR REPLACE,
so re-running is safe.

    python scripts/seed_postgres.py            # apply schema
    python scripts/seed_postgres.py --check    # verify connectivity + list tables

Override schema with --schema-file.  Override DATABASE_URL via env var (loaded
from .env if python-dotenv is installed).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Re-use the project's dotenv loading so .env is honoured.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def _ensure_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit(
            "DATABASE_URL is not set.  Put it in .env or export it before running."
        )
    return url


def cmd_apply(schema_path: Path) -> None:
    if not schema_path.exists():
        sys.exit(f"schema file not found: {schema_path}")

    sql = schema_path.read_text(encoding="utf-8")

    import psycopg  # noqa: E402
    url = _ensure_url()

    print(f"[seed] connecting to {url.split('@')[1].split('/')[0]}…")
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
        with conn.cursor() as cur:
            print(f"[seed] applying {schema_path.name} ({len(sql):,} bytes)…")
            cur.execute(sql)
            print("[seed] ✓ schema applied")
            # List tables we just touched.
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
            print(f"[seed] public tables: {', '.join(tables)}")


def cmd_check() -> None:
    import psycopg  # noqa: E402
    url = _ensure_url()
    with psycopg.connect(url, connect_timeout=10) as conn:
        cur = conn.cursor()
        cur.execute("SELECT version()")
        print("Connected:", cur.fetchone()[0])
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [r[0] for r in cur.fetchall()]
        if tables:
            print(f"public tables ({len(tables)}):")
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                n = cur.fetchone()[0]
                print(f"  {t:25s} {n} rows")
        else:
            print("public schema is empty — run without --check to apply the schema.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--schema-file",
        default=str(ROOT / "schema.sql"),
        help="Path to the schema SQL file (default: schema.sql)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Only print connectivity and current table list — no DDL.",
    )
    args = ap.parse_args()
    if args.check:
        cmd_check()
    else:
        cmd_apply(Path(args.schema_file))


if __name__ == "__main__":
    main()
