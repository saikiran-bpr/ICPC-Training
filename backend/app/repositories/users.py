"""
Repository for the `users` table + the helper joins it needs.

Skill rules applied:
  • data-n-plus-one    — `list_for_coach` resolves visible-contestant ids in
    one query using `WHERE team_id = ANY(...)` instead of one query per team
  • data-upsert        — `update_fields` uses dynamic SET only over a
    pre-validated field whitelist (no concatenated user input)
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from app.db import execute, fetch_all, fetch_one

# Columns returned by SELECT * minus password_hash — keeps the API surface
# safe even if a future bug stops calling public_user.
_PUBLIC_COLS = (
    "id, email, name, role, handle, institution, year_of_study, "
    "is_active, status, date_joined, last_login"
)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def get_by_id(conn: AsyncConnection, uid: int) -> dict[str, Any] | None:
    return await fetch_one(conn, f"SELECT {_PUBLIC_COLS} FROM users WHERE id = %s", (uid,))


async def get_by_email(conn: AsyncConnection, email: str) -> dict[str, Any] | None:
    """Includes password_hash — only the auth router should call this."""
    return await fetch_one(conn, "SELECT * FROM users WHERE email = %s", (email,))


async def email_exists(conn: AsyncConnection, email: str) -> bool:
    row = await fetch_one(conn, "SELECT 1 FROM users WHERE email = %s", (email,))
    return row is not None


async def list_all(
    conn: AsyncConnection,
    *,
    role: str | None = None,
    q: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Unscoped list. Caller applies role-based visibility filtering."""
    where: list[str] = []
    params: list[Any] = []
    if role:
        where.append("role = %s")
        params.append(role)
    if status:
        where.append("status = %s")
        params.append(status)
    if q:
        like = f"%{q}%"
        where.append("(name ILIKE %s OR email ILIKE %s OR handle ILIKE %s OR institution ILIKE %s)")
        params.extend([like, like, like, like])
    sql = f"SELECT {_PUBLIC_COLS} FROM users"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name"
    return await fetch_all(conn, sql, params)


async def search_users(
    conn: AsyncConnection,
    *,
    q: str | None,
    role: str | None,
    exclude_team_id: int | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Paginated, role-filterable search used by the team member picker.

    `exclude_team_id` removes users who are already a member OR coach of the
    given team — so the picker never offers a duplicate and the pagination
    count stays accurate as the team fills up.
    """
    where: list[str] = ["is_active = 1", "status = 'approved'"]
    params: list[Any] = []
    if role:
        where.append("role = %s")
        params.append(role)
    if q:
        like = f"%{q}%"
        where.append("(name ILIKE %s OR handle ILIKE %s)")
        params.extend([like, like])
    if exclude_team_id is not None:
        where.append(
            "id NOT IN ("
            "SELECT user_id FROM team_members WHERE team_id = %s "
            "UNION "
            "SELECT user_id FROM team_coaches WHERE team_id = %s"
            ")"
        )
        params.extend([exclude_team_id, exclude_team_id])

    where_sql = " AND ".join(where)

    count_row = await fetch_one(
        conn, f"SELECT COUNT(*) AS n FROM users WHERE {where_sql}", params
    )
    total = int(count_row["n"]) if count_row else 0

    rows = await fetch_all(
        conn,
        f"SELECT {_PUBLIC_COLS} FROM users WHERE {where_sql} "
        f"ORDER BY name LIMIT %s OFFSET %s",
        [*params, limit, offset],
    )
    return total, rows


async def list_pending(conn: AsyncConnection) -> list[dict[str, Any]]:
    """Signup requests awaiting admin review, newest first."""
    return await fetch_all(
        conn,
        f"SELECT {_PUBLIC_COLS} FROM users "
        f"WHERE status = 'pending' "
        f"ORDER BY date_joined DESC",
    )


async def count_pending(conn: AsyncConnection) -> int:
    row = await fetch_one(
        conn, "SELECT COUNT(*) AS n FROM users WHERE status = 'pending'"
    )
    return int(row["n"]) if row else 0


async def set_status(conn: AsyncConnection, uid: int, status: str) -> None:
    await execute(
        conn, "UPDATE users SET status = %s WHERE id = %s", (status, uid)
    )


async def delete_by_id(conn: AsyncConnection, uid: int) -> None:
    await execute(conn, "DELETE FROM users WHERE id = %s", (uid,))


async def coach_visible_user_ids(conn: AsyncConnection, coach_id: int) -> set[int]:
    """Return the ids of users (Admin/Coach + contestants on the coach's teams)
    that the coach is allowed to see in /api/users.

    One query, vs the legacy two-step (`SELECT team_ids` then `SELECT users
    WHERE team_id IN ...`).  data-n-plus-one skill rule applied.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT u.id
        FROM users u
        WHERE u.role IN ('Admin', 'Coach')
           OR u.id IN (
               SELECT tm.user_id
               FROM team_members tm
               JOIN team_coaches tc ON tc.team_id = tm.team_id
               WHERE tc.user_id = %s
           )
        """,
        (coach_id,),
    )
    return {r["id"] for r in rows}


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert(
    conn: AsyncConnection,
    *,
    email: str,
    password_hash: str,
    name: str,
    role: str,
    handle: str | None,
    institution: str | None,
    year_of_study: int | None,
) -> int:
    """Returns the new user id."""
    cur = await conn.execute(
        """
        INSERT INTO users (email, password_hash, name, role, handle, institution, year_of_study)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (email, password_hash, name, role, handle, institution, year_of_study),
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row["id"])


async def update_last_login(conn: AsyncConnection, uid: int) -> None:
    await execute(conn, "UPDATE users SET last_login = now() WHERE id = %s", (uid,))


async def update_password(conn: AsyncConnection, uid: int, new_hash: str) -> None:
    await execute(conn, "UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, uid))


# Whitelisted columns the PATCH /api/users/<uid> handler may write.
_EDITABLE_FIELDS = frozenset(
    {"name", "handle", "institution", "year_of_study", "role", "email", "is_active"}
)


async def update_fields(
    conn: AsyncConnection, uid: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    """Dynamic UPDATE over a whitelist.  Returns the updated row.

    Caller (router) already filters keys by role; this repo also clips to
    `_EDITABLE_FIELDS` as defence-in-depth.
    """
    safe = {k: v for k, v in fields.items() if k in _EDITABLE_FIELDS}
    if not safe:
        return await get_by_id(conn, uid)

    # Coerce is_active bool → smallint to match the column type.
    if "is_active" in safe and isinstance(safe["is_active"], bool):
        safe["is_active"] = 1 if safe["is_active"] else 0

    set_clause = ", ".join(f"{k} = %s" for k in safe)
    await execute(
        conn,
        f"UPDATE users SET {set_clause} WHERE id = %s",
        (*safe.values(), uid),
    )
    return await get_by_id(conn, uid)
