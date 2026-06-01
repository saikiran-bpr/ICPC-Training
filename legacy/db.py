"""
Thin psycopg adapter so the SQLite-flavoured Flask code can talk to
Supabase Postgres without rewriting every query.

The Flask app uses SQLite conventions everywhere:
  • qmark placeholders (`?`)              → rewritten to `%s` for psycopg
  • `INSERT OR IGNORE …`                  → rewritten to `INSERT … ON CONFLICT DO NOTHING`
  • `cur.lastrowid` after an INSERT       → emulated via `RETURNING id`
  • Row access by name (`row["email"]`)   → preserved through a dict-row wrapper
  • Auto-rollback on a failed statement   → otherwise Postgres aborts the whole transaction

DATABASE_URL must be set (Supabase Postgres URL).  No SQLite fallback —
Supabase is the only supported backend.

Usage:

    from db import connect, IntegrityError
    conn = connect()
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (uid,))
    print(cur.fetchone()["email"])
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.errors import IntegrityError as _PgIntegrityError
from psycopg.rows import dict_row

# python-dotenv: optional but useful for local dev (`python app.py`).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Re-exported under the legacy name so `except dbmod.IntegrityError`
# (and the older `except sqlite3.IntegrityError` migration alias) catch
# unique-violation errors raised by psycopg.
IntegrityError = _PgIntegrityError


def _postgres_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set.  Put your Supabase Postgres URL in .env "
            "(see .env.example) or export it before running Flask."
        )
    return url


def db_label() -> str:
    """Human-friendly description for logs.  Masks the password."""
    url = _postgres_url()
    try:
        scheme, rest = url.split("://", 1)
        creds, host = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"Postgres ({scheme}://{user}:***@{host})"
    except ValueError:
        return "Postgres (DATABASE_URL)"


# ---------------------------------------------------------------------------
# SQL rewriting
# ---------------------------------------------------------------------------

_QMARK_RE = re.compile(r"\?")

# SQLite's "INSERT OR IGNORE INTO …" — strip the OR IGNORE and append the
# Postgres ON CONFLICT clause below.
_INSERT_OR_IGNORE_RE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.IGNORECASE)

# Plain INSERT — used by lastrowid emulation to know whether to append RETURNING id.
_INSERT_HEAD_RE = re.compile(r"^\s*INSERT\s+(?:OR\s+REPLACE\s+)?INTO\b", re.IGNORECASE)
_HAS_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)
_HAS_ON_CONFLICT_RE = re.compile(r"\bON\s+CONFLICT\b", re.IGNORECASE)


def _rewrite_sql(sql: str) -> tuple[str, bool]:
    """Return (rewritten_sql, want_lastrowid).

    `want_lastrowid` is True when the caller is doing a plain INSERT that
    expects `cur.lastrowid` to work — we append `RETURNING id` so we can
    capture the new primary key from psycopg.
    """
    is_insert_or_ignore = bool(_INSERT_OR_IGNORE_RE.search(sql))
    if is_insert_or_ignore:
        sql = _INSERT_OR_IGNORE_RE.sub("INSERT INTO", sql)

    sql = _QMARK_RE.sub("%s", sql)

    want_lastrowid = False
    if _INSERT_HEAD_RE.search(sql) and not _HAS_RETURNING_RE.search(sql):
        if is_insert_or_ignore or _HAS_ON_CONFLICT_RE.search(sql):
            # ON CONFLICT path: insertion may be skipped, in which case
            # RETURNING returns zero rows and lastrowid stays None.
            sql = (
                sql.rstrip(" ;") + " ON CONFLICT DO NOTHING RETURNING id"
                if is_insert_or_ignore
                else sql.rstrip(" ;") + " RETURNING id"
            )
        else:
            sql = sql.rstrip(" ;") + " RETURNING id"
        want_lastrowid = True

    return sql, want_lastrowid


# ---------------------------------------------------------------------------
# Connection wrapper
# ---------------------------------------------------------------------------

class _PgConn:
    """psycopg connection wrapper mimicking the sqlite3.Connection surface
    the Flask app uses: `.execute`, `.executemany`, `.commit`, `.close`,
    `.row_factory` (accepted but ignored — we always return dict-like rows).
    """

    def __init__(self, dsn: str) -> None:
        # `prepare_threshold=None` disables named prepared statements so the
        # connection works against transaction-mode poolers (Supavisor /
        # PgBouncer in "transaction" mode), where prepared statements scoped
        # to a connection get lost across reuse.
        self._conn = psycopg.connect(
            dsn,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=10,
            autocommit=False,
        )
        self.row_factory: Any = None  # legacy attribute; ignored

    # ---- sqlite3.Connection-compatible API ---------------------------------

    def execute(self, sql: str, params: tuple | list = ()):
        rewritten, want_lastrowid = _rewrite_sql(sql)
        cur = self._conn.cursor()
        try:
            cur.execute(rewritten, tuple(params))
        except Exception:
            # A failed statement aborts the surrounding transaction in
            # Postgres ("current transaction is aborted, commands ignored
            # until end of transaction block").  Roll back so the next
            # `execute` on this connection can proceed — mirrors SQLite's
            # behaviour the Flask code was built against.
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise
        return _PgCursor(cur, want_lastrowid=want_lastrowid)

    def executemany(self, sql: str, seq: list):
        rewritten, _ = _rewrite_sql(sql)
        cur = self._conn.cursor()
        try:
            cur.executemany(rewritten, [tuple(p) for p in seq])
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise
        return _PgCursor(cur, want_lastrowid=False)

    def executescript(self, sql: str) -> None:
        """Run a multi-statement script.  Only used by the CLI seeder."""
        if not self._conn.autocommit:
            self._conn.commit()
        self._conn.autocommit = True
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
        finally:
            self._conn.autocommit = False

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


class _PgCursor:
    """psycopg cursor wrapper that:
      • returns dict-like rows from .fetchone()/.fetchall()
      • exposes `.lastrowid` populated from the RETURNING id we appended in
        `_rewrite_sql`.
    """

    def __init__(self, cur, *, want_lastrowid: bool) -> None:
        self._cur = cur
        self._lastrowid: Any = None
        if want_lastrowid and cur.description:
            try:
                row = cur.fetchone()
                if row is not None:
                    self._lastrowid = row.get("id")
            except Exception:
                self._lastrowid = None

    @property
    def lastrowid(self) -> Any:
        return self._lastrowid

    @property
    def rowcount(self) -> int:
        """Rows affected by the last UPDATE/DELETE.  Mirrors sqlite3.Cursor."""
        return self._cur.rowcount

    def fetchone(self):
        row = self._cur.fetchone()
        return _DictRow(row) if row is not None else None

    def fetchall(self):
        return [_DictRow(r) for r in self._cur.fetchall()]

    def __iter__(self):
        for r in self._cur:
            yield _DictRow(r)

    def close(self) -> None:
        self._cur.close()


class _DictRow:
    """Dict that also supports positional access — mirrors the row interface
    the Flask code was originally written against (sqlite3.Row)."""

    __slots__ = ("_d", "_keys")

    def __init__(self, d: dict) -> None:
        self._d = d
        self._keys = list(d.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._d[self._keys[key]]
        return self._d[key]

    def __contains__(self, key):
        return key in self._d

    def keys(self):
        return self._keys

    def __iter__(self):
        return iter(self._keys)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def items(self):
        return self._d.items()

    def __repr__(self) -> str:
        return f"_DictRow({self._d!r})"


# ---------------------------------------------------------------------------
# Public connect()
# ---------------------------------------------------------------------------

def connect(_unused: Any = None) -> _PgConn:
    """Open a new Postgres connection using DATABASE_URL.

    The legacy `db_path` argument is accepted for backward compatibility with
    older call sites and ignored.
    """
    return _PgConn(_postgres_url())
