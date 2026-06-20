"""
Contests router — `/api/contests/assigned` (the only one not under /api/bank).
legacy/app.py:1720-1862.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.deps import ConnDep, CurrentUser
from app.errors import forbidden, not_found
from app.repositories import contests as contests_repo
from app.schemas.contest import (
    AssignedContestOut,
    ContestTeamBreakdownOut,
    MemberEntryIn,
    MemberEntryOut,
)

router = APIRouter(prefix="/contests", tags=["contests"])


# ---------------------------------------------------------------------------
# GET /api/contests/assigned
# legacy: 1720-1862  — N+1-free port: hydrate batched + phase rollup batched
# ---------------------------------------------------------------------------

@router.get("/assigned", response_model=list[AssignedContestOut])
async def list_assigned_contests(me: CurrentUser, conn: ConnDep) -> list[dict]:
    rows = await contests_repo.list_assigned_for_viewer(conn, me)
    if not rows:
        return []

    # Hydrate (counts + assignees) and phase-rollup in parallel-friendly batches.
    hydrated = await contests_repo.hydrate_many(conn, rows)
    rollups = await contests_repo.phase_rollup_many(conn, hydrated, me)
    my_entries = await contests_repo.my_entry_map(
        conn, [c["id"] for c in hydrated], me["id"]
    )

    for c in hydrated:
        agg = rollups.get(c["id"], {})
        c["my_solved"] = agg.get("my_solved", 0)
        c["during_count"] = agg.get("during", 0)
        c["upsolve_count"] = agg.get("upsolve", 0)
        c["unphased_solved"] = agg.get("unphased_solved", 0)
        mine = my_entries.get(c["id"])
        c["my_status"] = mine["status"] if mine else None
        c["my_solved_count"] = mine["solved_count"] if mine else 0
    return hydrated


# ---------------------------------------------------------------------------
# Per-member status + reflections
# ---------------------------------------------------------------------------

@router.get("/{cid}/entries", response_model=list[MemberEntryOut])
async def list_contest_entries(
    me: CurrentUser,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
) -> list[dict]:
    """Team-visible status + reflections for a contest (role-scoped)."""
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found()
    return await contests_repo.list_member_entries(conn, cid, me)


@router.get("/{cid}/breakdown", response_model=list[ContestTeamBreakdownOut])
async def contest_team_breakdown(
    me: CurrentUser,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
) -> list[dict]:
    """Per-team member reflections (status, solved count, notes), role-scoped."""
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found()
    return await contests_repo.team_breakdown(conn, cid, me)


@router.put("/{cid}/entry", response_model=MemberEntryOut)
async def upsert_contest_entry(
    me: CurrentUser,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
    payload: MemberEntryIn,
) -> dict:
    """Create/replace the viewer's own status + reflection for a contest.
    Only a member of an assigned team may post an entry."""
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found()
    if not await contests_repo.contestant_can_see(conn, cid, me["id"]):
        raise forbidden("This contest is not assigned to you")
    await contests_repo.upsert_member_entry(
        conn,
        cid,
        me["id"],
        status=payload.status,
        solved_count=payload.solved_count,
        feedback=(payload.feedback or "").strip() or None,
        mistakes=(payload.mistakes or "").strip() or None,
    )
    return {
        "user_id": me["id"],
        "user_name": me["name"],
        "status": payload.status,
        "solved_count": payload.solved_count,
        "feedback": (payload.feedback or "").strip() or None,
        "mistakes": (payload.mistakes or "").strip() or None,
        "updated_at": None,
    }
