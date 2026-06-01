"""
Teams repository — all SQL touching the `teams`, `team_members`, and
`team_coaches` tables.

Skill rules applied:
  • data-n-plus-one — `list_with_members_coaches` batches the members + coaches
    fetch across all visible teams instead of 2 queries per team
    (legacy/app.py serialize_team did 2 sub-queries per row).
  • data-upsert     — INSERTs use plain INSERT (uniques are enforced at DB
    level; conflicts surface as IntegrityError → 409 in the router).
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from app.db import execute, fetch_all, fetch_one


# ---------------------------------------------------------------------------
# Plain reads
# ---------------------------------------------------------------------------

async def get_by_id(conn: AsyncConnection, tid: int) -> dict[str, Any] | None:
    return await fetch_one(conn, "SELECT * FROM teams WHERE id = %s", (tid,))


async def get_all(conn: AsyncConnection) -> list[dict[str, Any]]:
    return await fetch_all(conn, "SELECT * FROM teams ORDER BY name")


async def get_user_team_ids(conn: AsyncConnection, user_id: int) -> set[int]:
    """Team ids the user is a member of OR a coach of.  Single round trip.
    Used by `list_teams()` visibility filter — skill: data-n-plus-one."""
    rows = await fetch_all(
        conn,
        """
        SELECT team_id FROM team_members WHERE user_id = %s
        UNION
        SELECT team_id FROM team_coaches WHERE user_id = %s
        """,
        (user_id, user_id),
    )
    return {r["team_id"] for r in rows}


async def search_teams(
    conn: AsyncConnection,
    *,
    q: str | None,
    coach_id: int | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Paginated team search backing the assignment picker.

    When `coach_id` is given (the viewer is a Coach), results are restricted to
    teams that coach coaches via `team_coaches`.  Admins pass `coach_id=None`
    to search every active team.  Mirrors `users_repo.search_users`.
    """
    where: list[str] = ["is_active = 1"]
    params: list[Any] = []
    if coach_id is not None:
        where.append("id IN (SELECT team_id FROM team_coaches WHERE user_id = %s)")
        params.append(coach_id)
    if q:
        like = f"%{q}%"
        where.append("(name ILIKE %s OR institution ILIKE %s)")
        params.extend([like, like])

    where_sql = " AND ".join(where)
    count_row = await fetch_one(
        conn, f"SELECT COUNT(*) AS n FROM teams WHERE {where_sql}", params
    )
    total = int(count_row["n"]) if count_row else 0

    rows = await fetch_all(
        conn,
        f"SELECT id, name, institution FROM teams WHERE {where_sql} "
        f"ORDER BY name LIMIT %s OFFSET %s",
        [*params, limit, offset],
    )
    return total, rows


async def coached_team_ids(
    conn: AsyncConnection, coach_id: int, team_ids: list[int]
) -> set[int]:
    """Of `team_ids`, return the subset the given coach coaches.  One query —
    used to authorize assignment targets."""
    if not team_ids:
        return set()
    rows = await fetch_all(
        conn,
        "SELECT team_id FROM team_coaches WHERE user_id = %s AND team_id = ANY(%s)",
        (coach_id, team_ids),
    )
    return {r["team_id"] for r in rows}


# ---------------------------------------------------------------------------
# Hydration — N+1-free
# ---------------------------------------------------------------------------

async def hydrate_one(conn: AsyncConnection, team_row: dict[str, Any]) -> dict[str, Any]:
    """Add members + coaches + counts to a single team row.  Used by
    single-team endpoints (GET /teams/{id}, POST/PATCH responses)."""
    members = await fetch_all(
        conn,
        """
        SELECT u.id, u.name, u.email, u.handle, u.institution,
               tm.role_in_team, tm.joined_at
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.team_id = %s
        ORDER BY tm.role_in_team, u.name
        """,
        (team_row["id"],),
    )
    coaches = await fetch_all(
        conn,
        """
        SELECT u.id, u.name, u.email, u.role, tc.assigned_at
        FROM team_coaches tc
        JOIN users u ON tc.user_id = u.id
        WHERE tc.team_id = %s
        ORDER BY u.name
        """,
        (team_row["id"],),
    )
    return _shape_team(team_row, members, coaches)


async def hydrate_many(
    conn: AsyncConnection, team_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """N+1-free batch hydrate: one query for ALL members + one for ALL coaches
    across `team_rows`, then group in Python.  10 teams → 3 queries total
    (teams + members + coaches), vs the legacy 1 + 2×N pattern."""
    if not team_rows:
        return []
    team_ids = [t["id"] for t in team_rows]

    members = await fetch_all(
        conn,
        """
        SELECT tm.team_id, u.id, u.name, u.email, u.handle, u.institution,
               tm.role_in_team, tm.joined_at
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.team_id = ANY(%s)
        ORDER BY tm.team_id, tm.role_in_team, u.name
        """,
        (team_ids,),
    )
    coaches = await fetch_all(
        conn,
        """
        SELECT tc.team_id, u.id, u.name, u.email, u.role, tc.assigned_at
        FROM team_coaches tc
        JOIN users u ON tc.user_id = u.id
        WHERE tc.team_id = ANY(%s)
        ORDER BY tc.team_id, u.name
        """,
        (team_ids,),
    )

    members_by_team: dict[int, list[dict[str, Any]]] = {tid: [] for tid in team_ids}
    coaches_by_team: dict[int, list[dict[str, Any]]] = {tid: [] for tid in team_ids}
    for m in members:
        members_by_team[m["team_id"]].append({k: v for k, v in m.items() if k != "team_id"})
    for c in coaches:
        coaches_by_team[c["team_id"]].append({k: v for k, v in c.items() if k != "team_id"})

    return [
        _shape_team(t, members_by_team.get(t["id"], []), coaches_by_team.get(t["id"], []))
        for t in team_rows
    ]


def _shape_team(
    team_row: dict[str, Any],
    members: list[dict[str, Any]],
    coaches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine raw rows into the response shape the frontend's TeamCard expects."""
    d = dict(team_row)
    d["members"] = members
    d["coaches"] = coaches
    d["member_count"] = sum(1 for r in members if r["role_in_team"] == "Member")
    d["reserve_count"] = sum(1 for r in members if r["role_in_team"] == "Reserve")
    return d


# ---------------------------------------------------------------------------
# Writes — teams
# ---------------------------------------------------------------------------

async def insert(
    conn: AsyncConnection,
    *,
    name: str,
    institution: str | None,
    description: str | None,
    created_by: int,
) -> int:
    cur = await conn.execute(
        """
        INSERT INTO teams (name, institution, description, created_by)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (name, institution, description, created_by),
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row["id"])


_TEAM_EDITABLE = frozenset({"name", "institution", "description", "is_active"})


async def update_fields(
    conn: AsyncConnection, tid: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    safe = {k: v for k, v in fields.items() if k in _TEAM_EDITABLE}
    if not safe:
        return await get_by_id(conn, tid)
    if "is_active" in safe and isinstance(safe["is_active"], bool):
        safe["is_active"] = 1 if safe["is_active"] else 0
    set_clause = ", ".join(f"{k} = %s" for k in safe)
    affected = await execute(
        conn,
        f"UPDATE teams SET {set_clause} WHERE id = %s",
        (*safe.values(), tid),
    )
    if affected == 0:
        return None
    return await get_by_id(conn, tid)


async def delete(conn: AsyncConnection, tid: int) -> bool:
    """Returns True if a row was deleted, False if the team didn't exist."""
    affected = await execute(conn, "DELETE FROM teams WHERE id = %s", (tid,))
    return affected > 0


# ---------------------------------------------------------------------------
# Writes — members
# ---------------------------------------------------------------------------

async def member_counts(conn: AsyncConnection, tid: int, exclude_user: int | None = None) -> dict[str, int]:
    """Returns {"Member": n, "Reserve": n} for the team — used for cap checks.
    `exclude_user` lets the promote/demote handler ignore the user being moved."""
    sql = (
        "SELECT role_in_team, COUNT(*) AS n FROM team_members "
        "WHERE team_id = %s"
    )
    params: list[Any] = [tid]
    if exclude_user is not None:
        sql += " AND user_id != %s"
        params.append(exclude_user)
    sql += " GROUP BY role_in_team"
    rows = await fetch_all(conn, sql, params)
    return {r["role_in_team"]: r["n"] for r in rows}


async def member_exists(conn: AsyncConnection, tid: int, uid: int) -> bool:
    row = await fetch_one(
        conn,
        "SELECT 1 FROM team_members WHERE team_id = %s AND user_id = %s",
        (tid, uid),
    )
    return row is not None


async def add_member(
    conn: AsyncConnection, tid: int, uid: int, role_in_team: str
) -> None:
    await execute(
        conn,
        "INSERT INTO team_members (team_id, user_id, role_in_team) VALUES (%s, %s, %s)",
        (tid, uid, role_in_team),
    )


async def update_member_role(
    conn: AsyncConnection, tid: int, uid: int, role_in_team: str
) -> None:
    await execute(
        conn,
        "UPDATE team_members SET role_in_team = %s WHERE team_id = %s AND user_id = %s",
        (role_in_team, tid, uid),
    )


async def remove_member(conn: AsyncConnection, tid: int, uid: int) -> bool:
    affected = await execute(
        conn, "DELETE FROM team_members WHERE team_id = %s AND user_id = %s", (tid, uid)
    )
    return affected > 0


# ---------------------------------------------------------------------------
# Writes — coaches
# ---------------------------------------------------------------------------

async def add_coach(conn: AsyncConnection, tid: int, uid: int) -> None:
    await execute(
        conn,
        "INSERT INTO team_coaches (team_id, user_id) VALUES (%s, %s)",
        (tid, uid),
    )


async def remove_coach(conn: AsyncConnection, tid: int, uid: int) -> bool:
    affected = await execute(
        conn, "DELETE FROM team_coaches WHERE team_id = %s AND user_id = %s", (tid, uid)
    )
    return affected > 0
