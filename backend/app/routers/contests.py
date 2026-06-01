"""
Contests router — `/api/contests/assigned` (the only one not under /api/bank).
legacy/app.py:1720-1862.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import ConnDep, CurrentUser
from app.repositories import contests as contests_repo
from app.schemas.contest import AssignedContestOut

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

    for c in hydrated:
        agg = rollups.get(c["id"], {})
        c["my_solved"] = agg.get("my_solved", 0)
        c["during_count"] = agg.get("during", 0)
        c["upsolve_count"] = agg.get("upsolve", 0)
        c["unphased_solved"] = agg.get("unphased_solved", 0)
    return hydrated
