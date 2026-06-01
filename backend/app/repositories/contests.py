"""
Contests repository — all SQL touching `contests`, `contest_problems`,
`contest_users`, `contest_teams`.

Skill rules applied:
  • data-n-plus-one  — `hydrate_many` batches counts + assignees across all
    contests in 3 queries total (was 3×N in the legacy `_contest_summary`).
  • data-n-plus-one  — `phase_rollup_many` does ONE phase-rollup query
    grouped by (contest_id, problem_id) across all contests on the page,
    instead of one rollup query per contest.
  • data-upsert      — assign-from-bank + assign-contest use `ON CONFLICT
    (..) DO UPDATE SET via_contest = 0` so manual assignments always win
    over contest-derived ones.  Matches the legacy "stronger" semantics.
  • data-batch-inserts — `assign_contest` uses executemany for the per-
    problem junction inserts.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from app.db import execute, fetch_all, fetch_one


# ---------------------------------------------------------------------------
# Plain reads
# ---------------------------------------------------------------------------

async def get_by_id(conn: AsyncConnection, cid: int) -> dict[str, Any] | None:
    return await fetch_one(conn, "SELECT * FROM contests WHERE id = %s", (cid,))


async def list_all(
    conn: AsyncConnection, q: str | None = None
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if q:
        like = f"%{q}%"
        where.append("(name ILIKE %s OR platform ILIKE %s OR notes ILIKE %s)")
        params.extend([like, like, like])
    sql = "SELECT * FROM contests"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date_added DESC"
    return await fetch_all(conn, sql, params)


async def contestant_can_see(
    conn: AsyncConnection, contest_id: int, user_id: int
) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM contest_users WHERE contest_id = %s AND user_id = %s
        UNION ALL
        SELECT 1 FROM contest_teams ct
          JOIN team_members tm ON tm.team_id = ct.team_id
          WHERE ct.contest_id = %s AND tm.user_id = %s
        LIMIT 1
        """,
        (contest_id, user_id, contest_id, user_id),
    )
    return row is not None


async def list_assigned_for_viewer(
    conn: AsyncConnection, viewer: dict[str, Any]
) -> list[dict[str, Any]]:
    """Contests visible in the viewer's "Assigned Contests" tab."""
    role = viewer["role"]
    uid = viewer["id"]

    if role == "Admin":
        return await fetch_all(
            conn,
            """
            SELECT DISTINCT c.* FROM contests c
            WHERE c.id IN (SELECT contest_id FROM contest_users)
               OR c.id IN (SELECT contest_id FROM contest_teams)
            ORDER BY c.date_added DESC
            """,
        )
    if role == "Coach":
        return await fetch_all(
            conn,
            """
            SELECT DISTINCT c.* FROM contests c
            WHERE c.id IN (
                SELECT ct.contest_id FROM contest_teams ct
                JOIN team_coaches tc ON tc.team_id = ct.team_id
                WHERE tc.user_id = %s
            )
            OR c.id IN (
                SELECT cu.contest_id FROM contest_users cu
                JOIN team_members tm ON tm.user_id = cu.user_id
                JOIN team_coaches  tc ON tc.team_id = tm.team_id
                WHERE tc.user_id = %s
            )
            OR c.id IN (
                SELECT contest_id FROM contest_users WHERE user_id = %s
            )
            ORDER BY c.date_added DESC
            """,
            (uid, uid, uid),
        )
    # Contestant
    return await fetch_all(
        conn,
        """
        SELECT DISTINCT c.* FROM contests c
        WHERE c.id IN (SELECT contest_id FROM contest_users WHERE user_id = %s)
           OR c.id IN (
               SELECT ct.contest_id FROM contest_teams ct
               JOIN team_members tm ON tm.team_id = ct.team_id
               WHERE tm.user_id = %s
           )
        ORDER BY c.date_added DESC
        """,
        (uid, uid),
    )


async def get_problems_for_contest(
    conn: AsyncConnection, cid: int
) -> list[dict[str, Any]]:
    """Problems in a contest, in order_idx order (NULL last)."""
    return await fetch_all(
        conn,
        """
        SELECT p.*, cp.order_idx
        FROM contest_problems cp
        JOIN problems p ON p.id = cp.problem_id
        WHERE cp.contest_id = %s
        ORDER BY COALESCE(cp.order_idx, p.id), p.id
        """,
        (cid,),
    )


# ---------------------------------------------------------------------------
# N+1-free hydration
# ---------------------------------------------------------------------------

async def hydrate_many(
    conn: AsyncConnection, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Augment each contest with: problem_count, bank_problem_count (=
    unassigned), assigned_users, assigned_teams.  3 queries total."""
    if not rows:
        return []
    cids = [r["id"] for r in rows]

    # --- 1. Counts: total problems + how many have no per-problem assignment.
    counts_rows = await fetch_all(
        conn,
        """
        SELECT
            cp.contest_id,
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE p.id NOT IN (SELECT problem_id FROM problem_users)
                  AND p.id NOT IN (SELECT problem_id FROM problem_teams)
            ) AS unassigned
        FROM contest_problems cp
        JOIN problems p ON p.id = cp.problem_id
        WHERE cp.contest_id = ANY(%s)
        GROUP BY cp.contest_id
        """,
        (cids,),
    )
    counts_by_cid = {r["contest_id"]: r for r in counts_rows}

    # --- 2. Contest-level assigned users (across ALL contests on page).
    user_rows = await fetch_all(
        conn,
        """
        SELECT cu.contest_id, u.id, u.name, u.role
        FROM contest_users cu
        JOIN users u ON u.id = cu.user_id
        WHERE cu.contest_id = ANY(%s)
        ORDER BY cu.contest_id, u.name
        """,
        (cids,),
    )
    users_by_cid: dict[int, list[dict[str, Any]]] = {cid: [] for cid in cids}
    for u in user_rows:
        users_by_cid[u["contest_id"]].append(
            {"id": u["id"], "name": u["name"], "role": u["role"]}
        )

    # --- 3. Contest-level assigned teams.
    team_rows = await fetch_all(
        conn,
        """
        SELECT ct.contest_id, t.id, t.name, t.institution
        FROM contest_teams ct
        JOIN teams t ON t.id = ct.team_id
        WHERE ct.contest_id = ANY(%s)
        ORDER BY ct.contest_id, t.name
        """,
        (cids,),
    )
    teams_by_cid: dict[int, list[dict[str, Any]]] = {cid: [] for cid in cids}
    for t in team_rows:
        teams_by_cid[t["contest_id"]].append(
            {"id": t["id"], "name": t["name"], "institution": t["institution"]}
        )

    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        cnt = counts_by_cid.get(d["id"])
        d["problem_count"] = (cnt["total"] if cnt else 0) or 0
        d["bank_problem_count"] = (cnt["unassigned"] if cnt else 0) or 0
        d["assigned_users"] = users_by_cid.get(d["id"], [])
        d["assigned_teams"] = teams_by_cid.get(d["id"], [])
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Phase rollup (Assigned Contests tab) — batched across all contests
# ---------------------------------------------------------------------------

async def phase_rollup_many(
    conn: AsyncConnection,
    contests: list[dict[str, Any]],
    viewer: dict[str, Any],
) -> dict[int, dict[str, int]]:
    """Returns {contest_id: {my_solved, during, upsolve, unphased_solved}}.

    For each (contest, viewer-role) pair, resolves the set of user-ids whose
    attempts count toward the rollup, then issues a single grouped query
    spanning all contests.

    Legacy ran a per-contest rollup loop with 2-3 sub-queries per contest;
    this version is 2-3 queries total regardless of page size."""

    if not contests:
        return {}
    cids = [c["id"] for c in contests]
    role = viewer["role"]
    uid = viewer["id"]

    # --- Resolve member-id set per contest --------------------------------

    if role == "Contestant":
        # Teams viewer is on AND that the contest is assigned to.
        rows = await fetch_all(
            conn,
            """
            SELECT ct.contest_id, tm.user_id
            FROM contest_teams ct
            JOIN team_members tm ON tm.team_id = ct.team_id
            WHERE ct.contest_id = ANY(%s)
              AND tm.team_id IN (SELECT team_id FROM team_members WHERE user_id = %s)
            """,
            (cids, uid),
        )
        members_by_cid: dict[int, set[int]] = {cid: set() for cid in cids}
        for r in rows:
            members_by_cid[r["contest_id"]].add(r["user_id"])

        # Add self where individually assigned.
        own = await fetch_all(
            conn,
            "SELECT contest_id FROM contest_users WHERE user_id = %s "
            "AND contest_id = ANY(%s)",
            (uid, cids),
        )
        for r in own:
            members_by_cid[r["contest_id"]].add(uid)

        # Fallback to self when neither — matches legacy.
        for cid in cids:
            if not members_by_cid[cid]:
                members_by_cid[cid].add(uid)

    else:
        # Coach/Admin: everyone the contest is assigned to (users + team members).
        members_by_cid = {cid: set() for cid in cids}
        rows = await fetch_all(
            conn,
            "SELECT contest_id, user_id FROM contest_users WHERE contest_id = ANY(%s)",
            (cids,),
        )
        for r in rows:
            members_by_cid[r["contest_id"]].add(r["user_id"])
        rows = await fetch_all(
            conn,
            """
            SELECT ct.contest_id, tm.user_id
            FROM contest_teams ct
            JOIN team_members tm ON tm.team_id = ct.team_id
            WHERE ct.contest_id = ANY(%s)
            """,
            (cids,),
        )
        for r in rows:
            members_by_cid[r["contest_id"]].add(r["user_id"])

    # --- One grouped phase query across ALL contests + relevant users -----

    out: dict[int, dict[str, int]] = {
        cid: {
            "my_solved": 0,
            "during": 0,
            "upsolve": 0,
            "unphased_solved": 0,
        }
        for cid in cids
    }

    all_user_ids: set[int] = set()
    for ids in members_by_cid.values():
        all_user_ids.update(ids)
    if not all_user_ids:
        return out

    phase_rows = await fetch_all(
        conn,
        """
        SELECT
            cp.contest_id,
            cp.problem_id,
            pa.user_id,
            pa.attempt_status,
            pa.attempt_phase
        FROM contest_problems cp
        LEFT JOIN problem_attempts pa
               ON pa.problem_id = cp.problem_id
              AND pa.user_id = ANY(%s)
        WHERE cp.contest_id = ANY(%s)
        """,
        (list(all_user_ids), cids),
    )

    # Aggregate in Python — per (contest_id, problem_id) collapse to single
    # any_during / any_upsolve / any_accepted flags using ONLY attempts from
    # the contest's own member set.
    per_problem: dict[tuple[int, int], dict[str, bool]] = {}
    for r in phase_rows:
        cid = r["contest_id"]
        if r["user_id"] is None or r["user_id"] not in members_by_cid[cid]:
            continue
        key = (cid, r["problem_id"])
        flags = per_problem.setdefault(
            key, {"any_during": False, "any_upsolve": False, "any_accepted": False}
        )
        if r["attempt_status"] == "Accepted":
            flags["any_accepted"] = True
            if r["attempt_phase"] == "During Contest":
                flags["any_during"] = True
            elif r["attempt_phase"] == "Upsolve":
                flags["any_upsolve"] = True

    for (cid, _pid), flags in per_problem.items():
        if flags["any_during"]:
            out[cid]["during"] += 1
            out[cid]["my_solved"] += 1
        elif flags["any_upsolve"]:
            out[cid]["upsolve"] += 1
            out[cid]["my_solved"] += 1
        elif flags["any_accepted"]:
            out[cid]["unphased_solved"] += 1
            out[cid]["my_solved"] += 1
    return out


# ---------------------------------------------------------------------------
# Writes — contests
# ---------------------------------------------------------------------------

async def insert(
    conn: AsyncConnection,
    *,
    name: str,
    platform: str | None,
    contest_type: str | None,
    contest_year: int | None,
    url: str | None,
    notes: str | None,
    created_by: int,
) -> int:
    cur = await conn.execute(
        """
        INSERT INTO contests (name, platform, contest_type, contest_year, url, notes, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (name, platform, contest_type, contest_year, url, notes, created_by),
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row["id"])


_CONTEST_EDITABLE = frozenset(
    {"name", "platform", "contest_type", "contest_year", "url", "notes"}
)


async def update_fields(
    conn: AsyncConnection, cid: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    safe = {k: v for k, v in fields.items() if k in _CONTEST_EDITABLE}
    if not safe:
        return await get_by_id(conn, cid)
    set_clause = ", ".join(f"{k} = %s" for k in safe)
    await execute(
        conn,
        f"UPDATE contests SET {set_clause} WHERE id = %s",
        (*safe.values(), cid),
    )
    return await get_by_id(conn, cid)


async def delete(conn: AsyncConnection, cid: int) -> bool:
    affected = await execute(conn, "DELETE FROM contests WHERE id = %s", (cid,))
    return affected > 0


# ---------------------------------------------------------------------------
# Writes — contest_problems
# ---------------------------------------------------------------------------

async def add_problem(
    conn: AsyncConnection, cid: int, problem_id: int, order_idx: int | None
) -> None:
    await execute(
        conn,
        "INSERT INTO contest_problems (contest_id, problem_id, order_idx) VALUES (%s, %s, %s)",
        (cid, problem_id, order_idx),
    )


async def remove_problem(
    conn: AsyncConnection, cid: int, pid: int
) -> bool:
    affected = await execute(
        conn,
        "DELETE FROM contest_problems WHERE contest_id = %s AND problem_id = %s",
        (cid, pid),
    )
    return affected > 0


async def get_problem_ids_in_contest(
    conn: AsyncConnection, cid: int
) -> list[int]:
    rows = await fetch_all(
        conn,
        "SELECT problem_id FROM contest_problems WHERE contest_id = %s",
        (cid,),
    )
    return [r["problem_id"] for r in rows]


# ---------------------------------------------------------------------------
# Writes — contest_users / contest_teams (contest-level assignment)
# ---------------------------------------------------------------------------

async def add_contest_users(
    conn: AsyncConnection, cid: int, user_ids: list[int]
) -> None:
    if not user_ids:
        return
    await conn.cursor().executemany(
        "INSERT INTO contest_users (contest_id, user_id) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING",
        [(cid, uid) for uid in user_ids],
    )


async def add_contest_teams(
    conn: AsyncConnection, cid: int, team_ids: list[int]
) -> None:
    if not team_ids:
        return
    await conn.cursor().executemany(
        "INSERT INTO contest_teams (contest_id, team_id) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING",
        [(cid, tid) for tid in team_ids],
    )


# ---------------------------------------------------------------------------
# Bank assignment (problem-level, via_contest = 0)
# ---------------------------------------------------------------------------

async def assign_bank_problem(
    conn: AsyncConnection,
    problem_id: int,
    user_ids: list[int],
    team_ids: list[int],
) -> None:
    """Add (or downgrade existing contest-derived) per-problem assignments.

    Skill: data-upsert.  ON CONFLICT DO UPDATE makes manual assignments
    always win (via_contest = 0) — matches legacy semantics."""
    if user_ids:
        await conn.cursor().executemany(
            """
            INSERT INTO problem_users (problem_id, user_id, via_contest)
            VALUES (%s, %s, 0)
            ON CONFLICT (problem_id, user_id) DO UPDATE SET via_contest = 0
            """,
            [(problem_id, uid) for uid in user_ids],
        )
    if team_ids:
        await conn.cursor().executemany(
            """
            INSERT INTO problem_teams (problem_id, team_id, via_contest)
            VALUES (%s, %s, 0)
            ON CONFLICT (problem_id, team_id) DO UPDATE SET via_contest = 0
            """,
            [(problem_id, tid) for tid in team_ids],
        )


async def assign_contest_problems(
    conn: AsyncConnection,
    contest_id: int,
    problem_ids: list[int],
    user_ids: list[int],
    team_ids: list[int],
) -> int:
    """Bulk-assign every problem in `problem_ids` to the given users/teams
    with via_contest = 1.  ON CONFLICT DO NOTHING preserves any pre-existing
    direct (via_contest = 0) row — manual assignments are 'stronger'.

    Returns the number of problems processed.
    Skill: data-batch-inserts."""

    if user_ids:
        pairs = [(pid, uid) for pid in problem_ids for uid in user_ids]
        await conn.cursor().executemany(
            """
            INSERT INTO problem_users (problem_id, user_id, via_contest)
            VALUES (%s, %s, 1)
            ON CONFLICT DO NOTHING
            """,
            pairs,
        )
    if team_ids:
        pairs = [(pid, tid) for pid in problem_ids for tid in team_ids]
        await conn.cursor().executemany(
            """
            INSERT INTO problem_teams (problem_id, team_id, via_contest)
            VALUES (%s, %s, 1)
            ON CONFLICT DO NOTHING
            """,
            pairs,
        )

    # Also record the contest-level assignment so /api/contests/assigned can
    # surface the contest without re-deriving from junctions.
    await add_contest_users(conn, contest_id, user_ids)
    await add_contest_teams(conn, contest_id, team_ids)
    return len(problem_ids)
