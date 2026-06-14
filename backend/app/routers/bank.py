"""
Bank router — `/api/bank/*` endpoints.  10 endpoints total.

  • Problems: list + assign-from-bank (legacy 1567-1660)
  • Contests: list, get, create, update, delete + problem add/remove +
              bulk-assign (legacy 1865-2061)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from psycopg.errors import IntegrityError

from app.deps import (
    ConnDep,
    CurrentUser,
    RequireAdmin,
    RequireCoachOrAdmin,
)
from app.errors import bad_request, conflict, not_found
from app.repositories import contests as contests_repo
from app.repositories import problems as problems_repo
from app.schemas.contest import (
    AddProblemToContestIn,
    AssignContestResult,
    AssignIn,
    ContestCreate,
    ContestDeleted,
    ContestOut,
    ContestProblemRemoved,
    ContestUpdate,
    ContestWithProblems,
)
from app.schemas.problem import (
    BatchAssignIn,
    BatchAssignResult,
    ProblemFilters,
    ProblemListResponse,
    ProblemOut,
)

router = APIRouter(prefix="/bank", tags=["bank"])


# ===========================================================================
# Problems  (/api/bank/problems)
# ===========================================================================

@router.get("/problems", response_model=ProblemListResponse)
async def list_bank_problems(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    filters: Annotated[ProblemFilters, Query()],
) -> dict:
    """legacy: 1567-1615.  The bank shows standalone problems only
    (`from_contest = 0`).  Same Problem shape as /api/problems."""
    rows, total = await problems_repo.list_bank(conn, filters)
    hydrated = await problems_repo.hydrate_many(conn, rows, me)
    return {"total": total, "count": len(hydrated), "results": hydrated}


@router.post(
    "/problems/{problem_id}/assign",
    response_model=ProblemOut,
)
async def assign_from_bank(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    problem_id: Annotated[int, Path(ge=1)],
    payload: AssignIn,
) -> dict:
    """legacy: 1618-1657.  Hand a catalog problem to users/teams.  Problem
    stays in the bank (catalog is permanent)."""
    if await problems_repo.get_by_id(conn, problem_id) is None:
        raise not_found()

    if not payload.assigned_user_ids and not payload.assigned_team_ids:
        raise bad_request(
            "Provide at least one assigned_user_ids or assigned_team_ids"
        )
    try:
        await problems_repo.validate_assignment_targets(
            conn, payload.assigned_user_ids, payload.assigned_team_ids, me
        )
    except ValueError as e:
        raise bad_request(str(e)) from e

    await contests_repo.assign_bank_problem(
        conn,
        problem_id,
        payload.assigned_user_ids,
        payload.assigned_team_ids,
        me["id"],
    )

    row = await problems_repo.get_by_id(conn, problem_id)
    assert row is not None
    hydrated = await problems_repo.hydrate_many(conn, [row], me)
    return hydrated[0]


@router.post(
    "/problems/assign",
    response_model=BatchAssignResult,
)
async def batch_assign_from_bank(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    payload: BatchAssignIn,
) -> dict:
    """Batch-assign several catalog problems to users/teams in one call.

    Same per-problem semantics as `assign_from_bank` (additive merge — the bank
    entries stay, existing assignments are preserved).  Validation mirrors the
    single-problem endpoint: every problem id must exist, every assigned user
    must be a Contestant, and a Coach may only assign to teams they coach.
    """
    if not payload.problem_ids:
        raise bad_request("Provide at least one problem_id")
    if not payload.assigned_user_ids and not payload.assigned_team_ids:
        raise bad_request(
            "Provide at least one assigned_user_ids or assigned_team_ids"
        )

    # De-dupe while preserving order so the cross-product can't double-insert.
    problem_ids = list(dict.fromkeys(payload.problem_ids))

    found = await problems_repo.existing_ids(conn, problem_ids)
    missing = [pid for pid in problem_ids if pid not in found]
    if missing:
        raise bad_request(f"Unknown problem id(s): {missing}")

    try:
        await problems_repo.validate_assignment_targets(
            conn, payload.assigned_user_ids, payload.assigned_team_ids, me
        )
    except ValueError as e:
        raise bad_request(str(e)) from e

    await contests_repo.assign_bank_problems_batch(
        conn,
        problem_ids,
        payload.assigned_user_ids,
        payload.assigned_team_ids,
        me["id"],
    )

    return {
        "problems_assigned": len(problem_ids),
        "users_assigned": len(payload.assigned_user_ids),
        "teams_assigned": len(payload.assigned_team_ids),
    }


# ===========================================================================
# Contests  (/api/bank/contests)
# ===========================================================================

@router.get("/contests", response_model=list[ContestOut])
async def list_contests(
    _: RequireCoachOrAdmin,
    conn: ConnDep,
    q: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """legacy: 1865-1880."""
    rows = await contests_repo.list_all(conn, q=q)
    return await contests_repo.hydrate_many(conn, rows)


@router.get("/contests/{cid}", response_model=ContestWithProblems)
async def get_contest(
    me: CurrentUser,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
) -> dict:
    """legacy: 1883-1906.  Contestants can only fetch contests assigned to
    them (or to a team they belong to)."""
    row = await contests_repo.get_by_id(conn, cid)
    if row is None:
        raise not_found()
    if me["role"] == "Contestant" and not await contests_repo.contestant_can_see(
        conn, cid, me["id"]
    ):
        raise not_found()

    hydrated = (await contests_repo.hydrate_many(conn, [row]))[0]
    problem_rows = await contests_repo.get_problems_for_contest(conn, cid)
    hydrated["problems"] = await problems_repo.hydrate_many(conn, problem_rows, me)
    return hydrated


@router.post(
    "/contests",
    response_model=ContestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_contest(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    payload: ContestCreate,
) -> dict:
    """legacy: 1909-1930."""
    cid = await contests_repo.insert(
        conn,
        name=payload.name.strip(),
        platform=(payload.platform or "").strip() or None,
        contest_type=(payload.contest_type or "").strip() or None,
        contest_year=payload.contest_year,
        url=(payload.url or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        created_by=me["id"],
    )
    row = await contests_repo.get_by_id(conn, cid)
    assert row is not None
    return (await contests_repo.hydrate_many(conn, [row]))[0]


@router.patch("/contests/{cid}", response_model=ContestOut)
async def update_contest(
    _: RequireCoachOrAdmin,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
    payload: ContestUpdate,
) -> dict:
    """legacy: 1933-1948."""
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise bad_request("No editable fields supplied")
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found()
    updated = await contests_repo.update_fields(conn, cid, fields)
    if updated is None:
        raise not_found()
    return (await contests_repo.hydrate_many(conn, [updated]))[0]


@router.delete("/contests/{cid}", response_model=ContestDeleted)
async def delete_contest(
    _: RequireAdmin,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
) -> ContestDeleted:
    """legacy: 1951-1959  — Admin only."""
    if not await contests_repo.delete(conn, cid):
        raise not_found()
    return ContestDeleted(deleted=cid)


# --- Contest-problem links --------------------------------------------------

@router.post(
    "/contests/{cid}/problems",
    response_model=ContestWithProblems,
    status_code=status.HTTP_201_CREATED,
)
async def add_problem_to_contest(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
    payload: AddProblemToContestIn,
) -> dict:
    """legacy: 1962-1981."""
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found("Contest not found")
    if await problems_repo.get_by_id(conn, payload.problem_id) is None:
        raise not_found("Problem not found")
    try:
        await contests_repo.add_problem(conn, cid, payload.problem_id, payload.order_idx)
    except IntegrityError as e:
        raise conflict(str(e)) from e
    # Return the contest with its full (new) problem list — matches legacy.
    return await get_contest(me, conn, cid)


@router.delete(
    "/contests/{cid}/problems/{pid}",
    response_model=ContestProblemRemoved,
)
async def remove_problem_from_contest(
    _: RequireCoachOrAdmin,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
    pid: Annotated[int, Path(ge=1)],
) -> ContestProblemRemoved:
    """legacy: 1984-1995."""
    if not await contests_repo.remove_problem(conn, cid, pid):
        raise not_found()
    return ContestProblemRemoved(contest_id=cid, removed_problem_id=pid)


# --- Bulk-assign every problem in a contest ---------------------------------

@router.post(
    "/contests/{cid}/assign",
    response_model=AssignContestResult,
)
async def assign_contest(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    cid: Annotated[int, Path(ge=1)],
    payload: AssignIn,
) -> dict:
    """legacy: 1998-2061.  Each contest-problem gets a junction row with
    via_contest = 1, except when a manual via_contest = 0 row already exists
    (ON CONFLICT DO NOTHING preserves it)."""
    if await contests_repo.get_by_id(conn, cid) is None:
        raise not_found()
    if not payload.assigned_user_ids and not payload.assigned_team_ids:
        raise bad_request(
            "Provide at least one assigned_user_ids or assigned_team_ids"
        )
    try:
        await problems_repo.validate_assignment_targets(
            conn, payload.assigned_user_ids, payload.assigned_team_ids, me
        )
    except ValueError as e:
        raise bad_request(str(e)) from e

    pids = await contests_repo.get_problem_ids_in_contest(conn, cid)
    if not pids:
        raise conflict("Contest has no problems")

    affected = await contests_repo.assign_contest_problems(
        conn,
        cid,
        pids,
        payload.assigned_user_ids,
        payload.assigned_team_ids,
        me["id"],
    )

    row = await contests_repo.get_by_id(conn, cid)
    assert row is not None
    contest_out = (await contests_repo.hydrate_many(conn, [row]))[0]
    return {"contest": contest_out, "problems_assigned": affected}
