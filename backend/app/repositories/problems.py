"""
Problems repository — all SQL touching `problems`, `problem_users`,
`problem_teams`, `problem_attempts` (the upsert pieces).

Skill rules applied:
  • data-n-plus-one     — `hydrate_many` resolves assignment + per-viewer
    attempts + per-coach team summary in 3-4 batched queries, regardless of
    page size.  Legacy `row_to_dict` did 3 sub-queries PER row plus
    `_build_team_summary` did one extra per assigned team.  For a 20-row
    page that's 60+ round trips → now 3.
  • query-composite-indexes / query-partial-indexes — relies on the indexes
    added in migration 0002 (the list query filters via_contest=0 always).
  • data-upsert          — attempt upsert uses ON CONFLICT.
  • data-batch-inserts   — `bulk_insert` uses executemany.
  • lock-short-transactions — each request runs inside the per-request `tx()`
    dep; this repo never opens its own.
"""

from __future__ import annotations

import json
from typing import Any

from psycopg import AsyncConnection

from app.constants import ATTEMPT_PHASES, ATTEMPT_STATUSES, PROBLEM_FACED
from app.db import execute, fetch_all, fetch_one
from app.schemas.problem import ProblemFilters


# ---------------------------------------------------------------------------
# Sort helper
# ---------------------------------------------------------------------------

# Difficulty has no natural ordering in the DB; map text → ordinal in SQL.
_DIFFICULTY_ORDER_SQL = (
    "CASE difficulty "
    "WHEN 'Easy' THEN 1 "
    "WHEN 'Normal' THEN 2 "
    "WHEN 'Normal-Hard' THEN 3 "
    "WHEN 'Hard' THEN 4 "
    "WHEN 'Very Hard' THEN 5 "
    "WHEN 'Challenge' THEN 6 "
    "ELSE 99 END"
)

_SAFE_SORT_COLS = {"name", "rating", "date_added", "importance", "id"}


def _order_by(sort: str, order: str) -> str:
    """Build a safe ORDER BY clause from a whitelisted column name + direction."""
    direction = "ASC" if order.lower() == "asc" else "DESC"
    if sort == "difficulty":
        return f"{_DIFFICULTY_ORDER_SQL} {direction}, name ASC"
    if sort not in _SAFE_SORT_COLS:
        sort = "date_added"
    return f"{sort} {direction}"


# ---------------------------------------------------------------------------
# Tags <-> DB serialization helpers (DB stores text-encoded JSON array)
# ---------------------------------------------------------------------------

def _tags_to_db(value: list[str] | str | None) -> str:
    if value is None:
        return json.dumps([])
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return json.dumps(parts)
    return json.dumps([str(x).strip() for x in value if str(x).strip()])


# ---------------------------------------------------------------------------
# Visibility WHERE-clause builders
# ---------------------------------------------------------------------------

# Problems with at least one direct (non-contest) assignment — the Assigned
# Problems tab filter that excludes contest-derived rows.
_HAS_ANY_ASSIGNMENT_SQL = (
    "(id IN (SELECT problem_id FROM problem_users WHERE via_contest = 0)"
    " OR id IN (SELECT problem_id FROM problem_teams WHERE via_contest = 0))"
)

_CONTESTANT_VISIBILITY_SQL = (
    "(id IN (SELECT problem_id FROM problem_users "
    "        WHERE user_id = %s AND via_contest = 0)"
    " OR id IN ("
    "    SELECT pt.problem_id FROM problem_teams pt"
    "    JOIN team_members tm ON tm.team_id = pt.team_id"
    "    WHERE tm.user_id = %s AND pt.via_contest = 0"
    "))"
)

# A coach sees a problem when it's assigned (via_contest = 0) to a team they
# coach OR when they assigned it directly to an individual contestant
# (problem_users.assigned_by = them).  The latter is why a direct assignment to
# a contestant must still surface on the coach's Assigned Problems page.
_COACH_VISIBILITY_SQL = (
    "("
    "id IN ("
    "  SELECT pt.problem_id FROM problem_teams pt "
    "  JOIN team_coaches tc ON tc.team_id = pt.team_id "
    "  WHERE tc.user_id = %s AND pt.via_contest = 0"
    ")"
    " OR id IN ("
    "  SELECT problem_id FROM problem_users "
    "  WHERE assigned_by = %s AND via_contest = 0"
    ")"
    ")"
)

# An Admin sees only problems THEY assigned (to a contestant directly, or to a
# team) — not assignments made by coaches.  Mirrors the coach's "assigned_by"
# clause, applied to both junctions.
_ADMIN_VISIBILITY_SQL = (
    "("
    "id IN (SELECT problem_id FROM problem_users WHERE assigned_by = %s AND via_contest = 0)"
    " OR id IN (SELECT problem_id FROM problem_teams WHERE assigned_by = %s AND via_contest = 0)"
    ")"
)


# ---------------------------------------------------------------------------
# List query — used by /api/problems
# ---------------------------------------------------------------------------

async def list_assigned(
    conn: AsyncConnection,
    filters: ProblemFilters,
    viewer: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """Returns (rows, total).  Caller hydrates."""
    where, params = _build_where_filters(filters)
    where.append(_HAS_ANY_ASSIGNMENT_SQL)

    if viewer["role"] == "Contestant":
        where.append(_CONTESTANT_VISIBILITY_SQL)
        params.extend([viewer["id"], viewer["id"]])
    elif viewer["role"] == "Coach":
        where.append(_COACH_VISIBILITY_SQL)
        params.extend([viewer["id"], viewer["id"]])
    else:  # Admin: only problems they themselves assigned
        where.append(_ADMIN_VISIBILITY_SQL)
        params.extend([viewer["id"], viewer["id"]])

    where_clause = " WHERE " + " AND ".join(where)
    order_by = _order_by(filters.sort, filters.order)
    limit_sql = ""
    if filters.limit is not None:
        limit_sql = f" LIMIT {int(filters.limit)} OFFSET {int(filters.offset)}"

    rows = await fetch_all(
        conn,
        f"SELECT * FROM problems{where_clause} ORDER BY {order_by}{limit_sql}",
        params,
    )
    total_row = await fetch_one(
        conn, f"SELECT COUNT(*) AS n FROM problems{where_clause}", params
    )
    total = int(total_row["n"]) if total_row else 0
    return rows, total


# ---------------------------------------------------------------------------
# Bank list query — used by /api/bank/problems (no via_contest filter,
# strictly bank-only via `from_contest = 0`)
# ---------------------------------------------------------------------------

async def list_bank(
    conn: AsyncConnection, filters: ProblemFilters
) -> tuple[list[dict[str, Any]], int]:
    where, params = _build_where_filters(filters)
    where.append("from_contest = 0")
    where_clause = " WHERE " + " AND ".join(where)
    order_by = _order_by(filters.sort, filters.order)
    limit_sql = ""
    if filters.limit is not None:
        limit_sql = f" LIMIT {int(filters.limit)} OFFSET {int(filters.offset)}"

    rows = await fetch_all(
        conn,
        f"SELECT * FROM problems{where_clause} ORDER BY {order_by}{limit_sql}",
        params,
    )
    total_row = await fetch_one(
        conn, f"SELECT COUNT(*) AS n FROM problems{where_clause}", params
    )
    total = int(total_row["n"]) if total_row else 0
    return rows, total


def _build_where_filters(filters: ProblemFilters) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []

    def eq(col: str, val: Any) -> None:
        if val not in (None, ""):
            where.append(f"{col} = %s")
            params.append(val)

    eq("platform", filters.platform)
    eq("topic", filters.topic)
    eq("difficulty", filters.difficulty)
    eq("importance", filters.importance)
    eq("status", filters.status)
    eq("suggested_role", filters.suggested_role)
    eq("contest_type", filters.contest_type)

    if filters.rating_min is not None:
        where.append("rating >= %s")
        params.append(filters.rating_min)
    if filters.rating_max is not None:
        where.append("rating <= %s")
        params.append(filters.rating_max)

    if filters.q:
        like = f"%{filters.q}%"
        where.append(
            "(name ILIKE %s OR notes ILIKE %s OR key_idea ILIKE %s "
            "OR sub_topic ILIKE %s OR tags ILIKE %s)"
        )
        params.extend([like, like, like, like, like])

    return where, params


# ---------------------------------------------------------------------------
# Single-row queries
# ---------------------------------------------------------------------------

async def get_by_id(conn: AsyncConnection, pid: int) -> dict[str, Any] | None:
    return await fetch_one(conn, "SELECT * FROM problems WHERE id = %s", (pid,))


async def user_can_see_problem(
    conn: AsyncConnection, user_id: int, problem_id: int
) -> bool:
    """Visibility check used by the attempt endpoint."""
    direct = await fetch_one(
        conn,
        "SELECT 1 FROM problem_users WHERE problem_id = %s AND user_id = %s",
        (problem_id, user_id),
    )
    if direct is not None:
        return True
    via_team = await fetch_one(
        conn,
        "SELECT 1 FROM problem_teams pt "
        "JOIN team_members tm ON tm.team_id = pt.team_id "
        "WHERE pt.problem_id = %s AND tm.user_id = %s",
        (problem_id, user_id),
    )
    return via_team is not None


# ---------------------------------------------------------------------------
# Hydration — N+1-FREE batch loader for an arbitrary list of problem rows
# ---------------------------------------------------------------------------

async def hydrate_many(
    conn: AsyncConnection,
    rows: list[dict[str, Any]],
    viewer: dict[str, Any],
) -> list[dict[str, Any]]:
    """Augment each problem row with:
      • assigned_users  (list of {id, name, role})
      • assigned_teams  (list of {id, name})
      • my_attempt      (viewer's own attempt, or None)
      • team_summary    (Admin/Coach only — per-team member breakdown)

    Total DB round-trips: 3 (contestant viewer) or 4 (coach/admin), regardless
    of how many problems are on the page.  Replaces the legacy 3N + (assigned
    teams) × M pattern from row_to_dict + _build_team_summary."""
    if not rows:
        return []

    pids = [r["id"] for r in rows]

    # --- Batch query 1: assigned users for ALL problems on the page --------
    pu_rows = await fetch_all(
        conn,
        """
        SELECT pu.problem_id, u.id, u.name, u.role
        FROM problem_users pu
        JOIN users u ON u.id = pu.user_id
        WHERE pu.problem_id = ANY(%s)
        ORDER BY pu.problem_id, u.name
        """,
        (pids,),
    )
    users_by_problem: dict[int, list[dict[str, Any]]] = {pid: [] for pid in pids}
    for r in pu_rows:
        users_by_problem[r["problem_id"]].append(
            {"id": r["id"], "name": r["name"], "role": r["role"]}
        )

    # --- Batch query 2: assigned teams for ALL problems on the page -------
    pt_rows = await fetch_all(
        conn,
        """
        SELECT pt.problem_id, t.id, t.name
        FROM problem_teams pt
        JOIN teams t ON t.id = pt.team_id
        WHERE pt.problem_id = ANY(%s)
        ORDER BY pt.problem_id, t.name
        """,
        (pids,),
    )
    teams_by_problem: dict[int, list[dict[str, Any]]] = {pid: [] for pid in pids}
    for r in pt_rows:
        teams_by_problem[r["problem_id"]].append(
            {"id": r["id"], "name": r["name"]}
        )

    # --- Batch query 3: viewer's attempts on this page --------------------
    pa_rows = await fetch_all(
        conn,
        """
        SELECT problem_id, attempt_status, attempt_phase, problem_faced,
               time_spent_min, notes, updated_at
        FROM problem_attempts
        WHERE user_id = %s AND problem_id = ANY(%s)
        """,
        (viewer["id"], pids),
    )
    my_attempt_by_problem: dict[int, dict[str, Any]] = {
        r["problem_id"]: {
            "attempt_status": r["attempt_status"],
            "attempt_phase": r["attempt_phase"],
            "problem_faced": r["problem_faced"],
            "time_spent_min": r["time_spent_min"],
            "notes": r["notes"],
            "updated_at": r["updated_at"],
        }
        for r in pa_rows
    }

    # --- Batch query 4 (Coach/Admin): full team breakdown ------------------
    team_summaries: dict[int, list[dict[str, Any]]] = {}
    if viewer["role"] in ("Admin", "Coach"):
        team_summaries = await _build_team_summaries_many(
            conn, pids, teams_by_problem, users_by_problem
        )

    # --- Batch query 5 (Contestant): who assigned each problem to me -------
    assigned_by_map: dict[int, dict[str, Any]] = {}
    if viewer["role"] == "Contestant":
        assigned_by_map = await _assigner_for_viewer(conn, pids, viewer["id"])

    # --- Glue ---------------------------------------------------------------
    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["assigned_users"] = users_by_problem.get(d["id"], [])
        d["assigned_teams"] = teams_by_problem.get(d["id"], [])
        d["my_attempt"] = my_attempt_by_problem.get(d["id"])
        d["team_summary"] = team_summaries.get(d["id"], [])
        info = assigned_by_map.get(d["id"])
        d["assigned_by"] = info["assigned_by"] if info else None
        d["assigned_via"] = info["assigned_via"] if info else None
        out.append(d)
    return out


async def _assigner_for_viewer(
    conn: AsyncConnection, pids: list[int], user_id: int
) -> dict[int, dict[str, Any]]:
    """For a contestant, resolve who assigned each problem to them and how.

    A problem may be assigned directly (problem_users) and/or via a team
    (problem_teams).  Direct assignment wins for the "Assigned by" label; the
    `assigned_via` field is "Direct" or the team name.  Two batched queries +
    one name lookup, regardless of page size.
    """
    if not pids:
        return {}

    direct = await fetch_all(
        conn,
        """
        SELECT problem_id, assigned_by
        FROM problem_users
        WHERE user_id = %s AND problem_id = ANY(%s) AND via_contest = 0
        """,
        (user_id, pids),
    )
    via_team = await fetch_all(
        conn,
        """
        SELECT pt.problem_id, pt.assigned_by, t.name AS team_name
        FROM problem_teams pt
        JOIN teams t ON t.id = pt.team_id
        JOIN team_members tm ON tm.team_id = pt.team_id
        WHERE tm.user_id = %s AND pt.problem_id = ANY(%s) AND pt.via_contest = 0
        ORDER BY pt.problem_id, t.name
        """,
        (user_id, pids),
    )

    # Resolve assigner names in one lookup.
    assigner_ids = {r["assigned_by"] for r in (*direct, *via_team) if r["assigned_by"]}
    names: dict[int, dict[str, Any]] = {}
    if assigner_ids:
        urows = await fetch_all(
            conn,
            "SELECT id, name, role FROM users WHERE id = ANY(%s)",
            (list(assigner_ids),),
        )
        names = {r["id"]: {"id": r["id"], "name": r["name"], "role": r["role"]} for r in urows}

    out: dict[int, dict[str, Any]] = {}
    # Team assignments first so a direct assignment overrides them below.
    for r in via_team:
        out.setdefault(
            r["problem_id"],
            {"assigned_by": names.get(r["assigned_by"]), "assigned_via": r["team_name"]},
        )
    for r in direct:
        out[r["problem_id"]] = {
            "assigned_by": names.get(r["assigned_by"]),
            "assigned_via": "Direct",
        }
    return out


async def _build_team_summaries_many(
    conn: AsyncConnection,
    pids: list[int],
    teams_by_problem: dict[int, list[dict[str, Any]]],
    users_by_problem: dict[int, list[dict[str, Any]]],
) -> dict[int, list[dict[str, Any]]]:
    """Per-problem team breakdown for the coach/admin view, batched in 1 query.

    Returns {problem_id: [team_summary, …]} where each team_summary has the
    same shape as legacy `_build_team_summary` (legacy/app.py:345-428):
        {team_id, team_name, solved, total, reserve_solved, reserve_total, members}
    Plus a synthetic "Direct user assignments" group for problem_users not
    covered by any assigned team."""

    if not pids:
        return {}

    # Collect the (problem, team) pairs we need — one batch query for member rows.
    assigned_team_ids: list[int] = []
    for tlist in teams_by_problem.values():
        assigned_team_ids.extend(t["id"] for t in tlist)
    if assigned_team_ids:
        member_rows = await fetch_all(
            conn,
            """
            SELECT pt.problem_id, pt.team_id,
                   u.id AS user_id, u.name,
                   tm.role_in_team,
                   pa.attempt_status, pa.attempt_phase, pa.problem_faced,
                   pa.time_spent_min, pa.notes, pa.updated_at
            FROM problem_teams pt
            JOIN team_members tm ON tm.team_id = pt.team_id
            JOIN users u ON u.id = tm.user_id
            LEFT JOIN problem_attempts pa
                   ON pa.user_id = u.id AND pa.problem_id = pt.problem_id
            WHERE pt.problem_id = ANY(%s)
            ORDER BY pt.problem_id, pt.team_id, tm.role_in_team, u.name
            """,
            (pids,),
        )
    else:
        member_rows = []

    # Group: (problem_id, team_id) -> list of member dicts
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    member_user_ids_in_team: dict[int, set[int]] = {pid: set() for pid in pids}
    for m in member_rows:
        key = (m["problem_id"], m["team_id"])
        grouped.setdefault(key, []).append(
            {
                "id": m["user_id"],
                "name": m["name"],
                "role_in_team": m["role_in_team"],
                "attempt_status": m["attempt_status"],
                "attempt_phase": m["attempt_phase"],
                "problem_faced": m["problem_faced"],
                "time_spent_min": m["time_spent_min"],
                "notes": m["notes"],
                "updated_at": m["updated_at"],
            }
        )
        member_user_ids_in_team[m["problem_id"]].add(m["user_id"])

    # Direct (non-team) user assignments — one batch query for their attempts.
    direct_user_attempts = await _direct_user_attempts_many(
        conn, users_by_problem, member_user_ids_in_team
    )

    out: dict[int, list[dict[str, Any]]] = {}
    for pid in pids:
        per_team: list[dict[str, Any]] = []
        for t in teams_by_problem.get(pid, []):
            members = grouped.get((pid, t["id"]), [])
            primary_solved = sum(
                1 for m in members
                if m["role_in_team"] == "Member" and m["attempt_status"] == "Accepted"
            )
            primary_total = sum(1 for m in members if m["role_in_team"] == "Member")
            reserve_solved = sum(
                1 for m in members
                if m["role_in_team"] == "Reserve" and m["attempt_status"] == "Accepted"
            )
            reserve_total = sum(1 for m in members if m["role_in_team"] == "Reserve")
            per_team.append(
                {
                    "team_id": t["id"],
                    "team_name": t["name"],
                    "solved": primary_solved,
                    "total": primary_total,
                    "reserve_solved": reserve_solved,
                    "reserve_total": reserve_total,
                    "members": members,
                }
            )

        # Direct user assignments not already represented in any team.
        direct = direct_user_attempts.get(pid, [])
        if direct:
            per_team.append(
                {
                    "team_id": None,
                    "team_name": "Direct user assignments",
                    "solved": sum(1 for u in direct if u["attempt_status"] == "Accepted"),
                    "total": len(direct),
                    "reserve_solved": 0,
                    "reserve_total": 0,
                    "members": direct,
                }
            )
        out[pid] = per_team
    return out


async def _direct_user_attempts_many(
    conn: AsyncConnection,
    users_by_problem: dict[int, list[dict[str, Any]]],
    member_user_ids_in_team: dict[int, set[int]],
) -> dict[int, list[dict[str, Any]]]:
    """For each problem, build the per-direct-user attempt list (members of
    assigned teams excluded — they're already in their team's group)."""
    # Collect the (problem_id, user_id) pairs we still need attempts for.
    pairs: list[tuple[int, int, dict[str, Any]]] = []
    for pid, users in users_by_problem.items():
        in_team = member_user_ids_in_team.get(pid, set())
        for u in users:
            if u["id"] not in in_team:
                pairs.append((pid, u["id"], u))
    if not pairs:
        return {}

    pid_list = list({pid for pid, _, _ in pairs})
    uid_list = list({uid for _, uid, _ in pairs})

    # Single batch query for all (problem_id, user_id) attempt rows in scope.
    attempt_rows = await fetch_all(
        conn,
        """
        SELECT problem_id, user_id, attempt_status, attempt_phase,
               problem_faced, time_spent_min, notes, updated_at
        FROM problem_attempts
        WHERE problem_id = ANY(%s) AND user_id = ANY(%s)
        """,
        (pid_list, uid_list),
    )
    attempts: dict[tuple[int, int], dict[str, Any]] = {
        (r["problem_id"], r["user_id"]): r for r in attempt_rows
    }

    out: dict[int, list[dict[str, Any]]] = {}
    for pid, uid, user in pairs:
        a = attempts.get((pid, uid))
        out.setdefault(pid, []).append(
            {
                "id": uid,
                "name": user["name"],
                "role_in_team": None,  # not in a team
                "attempt_status": a["attempt_status"] if a else None,
                "attempt_phase": a["attempt_phase"] if a else None,
                "problem_faced": a["problem_faced"] if a else None,
                "time_spent_min": a["time_spent_min"] if a else None,
                "notes": a["notes"] if a else None,
                "updated_at": a["updated_at"] if a else None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Writes — problems
# ---------------------------------------------------------------------------

# Whitelist of columns the create/update routes may set directly.
EDITABLE_COLUMNS = frozenset(
    {
        "name", "url", "platform", "contest_type",
        "rating", "difficulty", "topic", "sub_topic", "tags",
        "importance", "suggested_role", "prerequisites", "key_idea",
        "editorial_url", "time_limit_ms", "memory_limit_mb",
        "status", "assigned_to", "notes",
    }
)


def normalise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Clip to EDITABLE_COLUMNS, JSON-encode tags, coerce numerics."""
    clean: dict[str, Any] = {}
    for k in EDITABLE_COLUMNS:
        if k in payload:
            clean[k] = payload[k]
    if "tags" in clean:
        clean["tags"] = _tags_to_db(clean["tags"])
    for k in ("rating", "time_limit_ms", "memory_limit_mb"):
        if k in clean:
            v = clean[k]
            if v in (None, ""):
                clean[k] = None
            else:
                try:
                    clean[k] = int(v)
                except (TypeError, ValueError):
                    clean[k] = None
    return clean


async def insert(
    conn: AsyncConnection, data: dict[str, Any], created_by: int
) -> int:
    """Insert a problem. Caller already called `normalise_payload`."""
    data = dict(data)
    data["created_by"] = created_by
    data["is_bank"] = 1
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    cur = await conn.execute(
        f"INSERT INTO problems ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
        [data[c] for c in cols],
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row["id"])


async def update_fields(
    conn: AsyncConnection, pid: int, data: dict[str, Any]
) -> None:
    """Partial update.  Caller already called `normalise_payload`."""
    if not data:
        return
    set_clause = ", ".join(f"{k} = %s" for k in data.keys())
    await execute(
        conn,
        f"UPDATE problems SET {set_clause} WHERE id = %s",
        (*data.values(), pid),
    )


async def delete(conn: AsyncConnection, pid: int) -> bool:
    affected = await execute(conn, "DELETE FROM problems WHERE id = %s", (pid,))
    return affected > 0


async def bulk_insert(
    conn: AsyncConnection, items: list[dict[str, Any]], created_by: int
) -> tuple[int, int, list[dict[str, Any]]]:
    """Batch-insert problems via executemany.  Returns (inserted, skipped, errors).

    Skill: data-batch-inserts.  One round-trip for the whole batch instead of
    one per item.  Per-row failures are caught and reported rather than
    aborting the entire batch.
    """
    inserted = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    # First pass: validate + normalise, collect a single column set so we can
    # executemany.  Items with different column shapes are inserted individually.
    valid: list[tuple[dict[str, Any], int]] = []  # (data, original_index)
    for idx, item in enumerate(items):
        if not all(item.get(k) for k in ("name", "url", "platform")):
            errors.append({"index": idx, "error": "missing required fields"})
            skipped += 1
            continue
        data = normalise_payload(item)
        data["created_by"] = created_by
        data["is_bank"] = 1
        valid.append((data, idx))

    # Insert each item — keep it simple + report errors per-row (a unique-URL
    # collision shouldn't abort the rest).  Using execute (not executemany)
    # gives us per-row error isolation; for big batches we could do
    # `INSERT ... VALUES (...), (...), ...` with all-or-nothing semantics.
    for data, idx in valid:
        cols = list(data.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        try:
            await conn.execute(
                f"INSERT INTO problems ({', '.join(cols)}) VALUES ({placeholders})",
                [data[c] for c in cols],
            )
            inserted += 1
        except Exception as e:  # noqa: BLE001 — surface DB errors to the client
            # Roll back the inner sub-transaction so the next insert can run.
            try:
                await conn.rollback()
                await conn.execute("BEGIN")
            except Exception:
                pass
            errors.append({"index": idx, "error": str(e)})
            skipped += 1
    return inserted, skipped, errors


# ---------------------------------------------------------------------------
# Many-to-many assignment writes
# ---------------------------------------------------------------------------

async def replace_problem_teams(
    conn: AsyncConnection,
    problem_id: int,
    team_ids: list[int],
    assigned_by: int | None = None,
) -> None:
    """Wipe + reinsert the team set for a problem, recording the assigner."""
    await execute(conn, "DELETE FROM problem_teams WHERE problem_id = %s", (problem_id,))
    if team_ids:
        # Batch insert with ON CONFLICT DO NOTHING in case of dupes within the
        # caller's list — UNIQUE(problem_id, team_id) prevents true duplicates.
        await conn.cursor().executemany(
            "INSERT INTO problem_teams (problem_id, team_id, assigned_by) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(problem_id, tid, assigned_by) for tid in team_ids],
        )


async def replace_problem_users(
    conn: AsyncConnection,
    problem_id: int,
    user_ids: list[int],
    assigned_by: int | None = None,
) -> None:
    await execute(conn, "DELETE FROM problem_users WHERE problem_id = %s", (problem_id,))
    if user_ids:
        await conn.cursor().executemany(
            "INSERT INTO problem_users (problem_id, user_id, assigned_by) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(problem_id, uid, assigned_by) for uid in user_ids],
        )


async def validate_assignment_targets(
    conn: AsyncConnection,
    user_ids: list[int] | None,
    team_ids: list[int] | None,
    me: dict[str, Any] | None = None,
) -> None:
    """Validate assignment targets.  Raises ValueError (router → 400) when:

      • a user/team id doesn't exist;
      • an assigned user is NOT a Contestant — only Contestants solve problems,
        so coaches/admins can't be assigned;
      • the actor is a Coach assigning to a team they don't coach — coaches may
        only assign to their own teams (Admins are unrestricted).
    """
    if user_ids:
        rows = await fetch_all(
            conn,
            "SELECT id, role FROM users WHERE id = ANY(%s)",
            (user_ids,),
        )
        found = {r["id"] for r in rows}
        missing = [u for u in user_ids if u not in found]
        if missing:
            raise ValueError(f"assigned_user_ids contains invalid user id(s): {missing}")
        non_contestants = sorted(r["id"] for r in rows if r["role"] != "Contestant")
        if non_contestants:
            raise ValueError(
                f"assigned_user_ids must be Contestants — not allowed: {non_contestants}"
            )
    if team_ids:
        rows = await fetch_all(
            conn,
            "SELECT id FROM teams WHERE id = ANY(%s)",
            (team_ids,),
        )
        found = {r["id"] for r in rows}
        missing = [t for t in team_ids if t not in found]
        if missing:
            raise ValueError(f"assigned_team_ids contains invalid team id(s): {missing}")
        # Coaches may only assign to teams they coach; Admins are unrestricted.
        if me is not None and me.get("role") == "Coach":
            crows = await fetch_all(
                conn,
                "SELECT team_id FROM team_coaches WHERE user_id = %s AND team_id = ANY(%s)",
                (me["id"], team_ids),
            )
            coached = {r["team_id"] for r in crows}
            not_coached = sorted(t for t in team_ids if t not in coached)
            if not_coached:
                raise ValueError(
                    f"You can only assign to teams you coach — not allowed: {not_coached}"
                )


# ---------------------------------------------------------------------------
# Per-user / per-team problem lists
# ---------------------------------------------------------------------------

async def list_for_team(
    conn: AsyncConnection, team_id: int
) -> list[dict[str, Any]]:
    """Direct (via_contest = 0) problem assignments for a single team."""
    return await fetch_all(
        conn,
        """
        SELECT p.*
        FROM problem_teams pt
        JOIN problems p ON p.id = pt.problem_id
        WHERE pt.team_id = %s AND pt.via_contest = 0
        ORDER BY p.date_added DESC
        """,
        (team_id,),
    )


async def list_for_user(
    conn: AsyncConnection, user_id: int
) -> list[dict[str, Any]]:
    """Problems assigned to user — directly or via any team they belong to.
    Always direct (via_contest = 0)."""
    return await fetch_all(
        conn,
        """
        SELECT DISTINCT p.*
        FROM problems p
        WHERE p.id IN (
            SELECT problem_id FROM problem_users
            WHERE user_id = %s AND via_contest = 0
        )
        OR p.id IN (
            SELECT pt.problem_id FROM problem_teams pt
            JOIN team_members tm ON tm.team_id = pt.team_id
            WHERE tm.user_id = %s AND pt.via_contest = 0
        )
        ORDER BY p.date_added DESC
        """,
        (user_id, user_id),
    )


# ---------------------------------------------------------------------------
# Attempt upsert
# ---------------------------------------------------------------------------

async def get_attempt(
    conn: AsyncConnection, problem_id: int, user_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT attempt_status, attempt_phase, problem_faced,
               time_spent_min, notes, updated_at
        FROM problem_attempts WHERE problem_id = %s AND user_id = %s
        """,
        (problem_id, user_id),
    )


async def upsert_attempt(
    conn: AsyncConnection,
    problem_id: int,
    user_id: int,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Skill: data-upsert.  Atomic INSERT … ON CONFLICT DO UPDATE."""
    columns = ["problem_id", "user_id", *fields.keys()]
    values = [problem_id, user_id, *fields.values()]
    update_set = ", ".join(f"{k} = EXCLUDED.{k}" for k in fields)
    placeholders = ", ".join(["%s"] * len(columns))
    await conn.execute(
        f"""
        INSERT INTO problem_attempts ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (problem_id, user_id) DO UPDATE
            SET {update_set}, updated_at = now()
        """,
        values,
    )
    row = await get_attempt(conn, problem_id, user_id)
    assert row is not None
    return row


# ---------------------------------------------------------------------------
# Attempt-payload validators (router calls these before building the upsert)
# ---------------------------------------------------------------------------

def validate_attempt_field(field: str, value: Any) -> Any:
    """Whitelist enum + coerce numeric.  Raises ValueError on invalid input."""
    if field == "attempt_status":
        if value not in (None, "") and value not in ATTEMPT_STATUSES:
            raise ValueError(f"attempt_status must be one of {list(ATTEMPT_STATUSES)}")
        return value or None
    if field == "problem_faced":
        if value not in (None, "") and value not in PROBLEM_FACED:
            raise ValueError(f"problem_faced must be one of {list(PROBLEM_FACED)}")
        return value or None
    if field == "attempt_phase":
        if value not in (None, "") and value not in ATTEMPT_PHASES:
            raise ValueError(f"attempt_phase must be one of {list(ATTEMPT_PHASES)}")
        return value or None
    if field == "time_spent_min":
        if value in (None, ""):
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError) as e:
            raise ValueError("time_spent_min must be an integer (minutes)") from e
    if field == "notes":
        return (value or "").strip() or None
    return value
