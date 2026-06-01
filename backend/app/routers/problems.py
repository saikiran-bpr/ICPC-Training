"""
Problems router — 7 endpoints, port of legacy:
  • GET    /api/problems              (2112-2192)
  • GET    /api/problems/<id>         (2195-2207)
  • POST   /api/problems               (2210-2247)
  • PUT/PATCH /api/problems/<id>      (2307-2335)
  • DELETE /api/problems/<id>         (2338-2346)
  • POST   /api/problems/bulk          (2349-2376)
  • PUT    /api/problems/<id>/attempt (875-973) — Accepted requires phase+time+notes
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from psycopg.errors import IntegrityError

from app.constants import ATTEMPT_PHASES
from app.deps import ConnDep, CurrentUser, RequireCoachOrAdmin, can_manage_problem
from app.errors import bad_request, conflict, forbidden, not_found
from app.repositories import problems as problems_repo
from app.schemas.attempt import AttemptIn, AttemptOut
from app.schemas.problem import (
    BulkCreateIn,
    BulkCreateResult,
    ProblemDeleted,
    ProblemFilters,
    ProblemListResponse,
    ProblemOut,
    ProblemWrite,
)
from app.services import lookup as lookup_service

router = APIRouter(prefix="/problems", tags=["problems"])


# ---------------------------------------------------------------------------
# GET /api/problems  — list assigned problems for the current viewer
# legacy: 2112-2192
# ---------------------------------------------------------------------------

@router.get("", response_model=ProblemListResponse)
async def list_problems(
    me: CurrentUser,
    conn: ConnDep,
    filters: Annotated[ProblemFilters, Query()],
) -> dict:
    rows, total = await problems_repo.list_assigned(conn, filters, me)
    hydrated = await problems_repo.hydrate_many(conn, rows, me)
    return {"total": total, "count": len(hydrated), "results": hydrated}


# ---------------------------------------------------------------------------
# GET /api/problems/{id}
# legacy: 2195-2207
# ---------------------------------------------------------------------------

@router.get("/{problem_id}", response_model=ProblemOut)
async def get_problem(
    me: CurrentUser,
    conn: ConnDep,
    problem_id: Annotated[int, Path(ge=1)],
) -> dict:
    row = await problems_repo.get_by_id(conn, problem_id)
    if row is None:
        raise not_found()
    if me["role"] == "Contestant" and not await problems_repo.user_can_see_problem(
        conn, me["id"], problem_id
    ):
        raise not_found()
    hydrated = await problems_repo.hydrate_many(conn, [row], me)
    return hydrated[0]


# ---------------------------------------------------------------------------
# POST /api/problems  — Admin/Coach create
# legacy: 2210-2247
# ---------------------------------------------------------------------------

@router.post("", response_model=ProblemOut, status_code=status.HTTP_201_CREATED)
async def create_problem(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    payload: ProblemWrite,
) -> dict:
    if not payload.url or not payload.url.strip():
        raise bad_request("url is required")
    if not payload.platform:
        raise bad_request("platform is required")

    body = payload.model_dump(exclude_unset=True)

    # Auto-fetch name if not supplied — mirrors legacy behaviour.
    if not (body.get("name") or "").strip():
        fetched = await lookup_service.fetch_name_only(body["url"])
        if not fetched:
            raise bad_request("Could not fetch a name from that URL — please provide one.")
        body["name"] = fetched

    user_ids = body.pop("assigned_user_ids", None)
    team_ids = body.pop("assigned_team_ids", None)
    try:
        await problems_repo.validate_assignment_targets(conn, user_ids, team_ids)
    except ValueError as e:
        raise bad_request(str(e)) from e

    data = problems_repo.normalise_payload(body)
    try:
        pid = await problems_repo.insert(conn, data, created_by=me["id"])
        if user_ids is not None:
            await problems_repo.replace_problem_users(conn, pid, user_ids)
        if team_ids is not None:
            await problems_repo.replace_problem_teams(conn, pid, team_ids)
    except IntegrityError as e:
        raise conflict(f"Integrity error: {e}") from e

    row = await problems_repo.get_by_id(conn, pid)
    assert row is not None
    hydrated = await problems_repo.hydrate_many(conn, [row], me)
    return hydrated[0]


# ---------------------------------------------------------------------------
# PUT/PATCH /api/problems/{id}  — Admin/Coach update
# legacy: 2307-2335
# ---------------------------------------------------------------------------

@router.put("/{problem_id}", response_model=ProblemOut)
@router.patch("/{problem_id}", response_model=ProblemOut)
async def update_problem(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    problem_id: Annotated[int, Path(ge=1)],
    payload: ProblemWrite,
) -> dict:
    if await problems_repo.get_by_id(conn, problem_id) is None:
        raise not_found()
    if not await can_manage_problem(conn, problem_id, me):
        raise forbidden("You can only edit problems you created")

    body = payload.model_dump(exclude_unset=True)
    user_ids = body.pop("assigned_user_ids", None)
    team_ids = body.pop("assigned_team_ids", None)
    data = problems_repo.normalise_payload(body)

    if not data and user_ids is None and team_ids is None:
        raise bad_request("No editable fields supplied")

    try:
        await problems_repo.validate_assignment_targets(conn, user_ids, team_ids)
    except ValueError as e:
        raise bad_request(str(e)) from e

    try:
        if data:
            await problems_repo.update_fields(conn, problem_id, data)
        if user_ids is not None:
            await problems_repo.replace_problem_users(conn, problem_id, user_ids)
        if team_ids is not None:
            await problems_repo.replace_problem_teams(conn, problem_id, team_ids)
    except IntegrityError as e:
        raise conflict(f"Integrity error: {e}") from e

    row = await problems_repo.get_by_id(conn, problem_id)
    assert row is not None
    hydrated = await problems_repo.hydrate_many(conn, [row], me)
    return hydrated[0]


# ---------------------------------------------------------------------------
# DELETE /api/problems/{id}
# legacy: 2338-2346
# ---------------------------------------------------------------------------

@router.delete("/{problem_id}", response_model=ProblemDeleted)
async def delete_problem(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    problem_id: Annotated[int, Path(ge=1)],
) -> ProblemDeleted:
    if await problems_repo.get_by_id(conn, problem_id) is None:
        raise not_found()
    if not await can_manage_problem(conn, problem_id, me):
        raise forbidden("You can only delete problems you created")
    if not await problems_repo.delete(conn, problem_id):
        raise not_found()
    return ProblemDeleted(deleted=problem_id)


# ---------------------------------------------------------------------------
# POST /api/problems/bulk
# legacy: 2349-2376
# ---------------------------------------------------------------------------

@router.post("/bulk", response_model=BulkCreateResult)
async def bulk_create(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    payload: BulkCreateIn,
) -> BulkCreateResult:
    inserted, skipped, errors = await problems_repo.bulk_insert(
        conn, payload.items, created_by=me["id"]
    )
    return BulkCreateResult(inserted=inserted, skipped=skipped, errors=errors)


# ---------------------------------------------------------------------------
# PUT /api/problems/{id}/attempt
# legacy: 875-973
# ---------------------------------------------------------------------------

@router.put("/{problem_id}/attempt", response_model=AttemptOut)
async def upsert_attempt(
    me: CurrentUser,
    conn: ConnDep,
    problem_id: Annotated[int, Path(ge=1)],
    payload: AttemptIn,
) -> dict:
    if await problems_repo.get_by_id(conn, problem_id) is None:
        raise not_found()

    # Contestants are limited to problems they can see; Admin/Coach can record
    # attempts on anything for themselves.
    if me["role"] == "Contestant" and not await problems_repo.user_can_see_problem(
        conn, me["id"], problem_id
    ):
        raise not_found()

    # --- field-by-field validation --------------------------------------
    fields: dict = {}
    raw = payload.model_dump(exclude_unset=True)
    for field in ("attempt_status", "problem_faced", "attempt_phase",
                  "time_spent_min", "notes"):
        if field in raw:
            try:
                fields[field] = problems_repo.validate_attempt_field(field, raw[field])
            except ValueError as e:
                raise bad_request(str(e)) from e

    if not fields:
        raise bad_request("No fields to update")

    # --- "Accepted requires phase + time + notes" gate -------------------
    if fields.get("attempt_status") == "Accepted":
        existing = await problems_repo.get_attempt(conn, problem_id, me["id"])
        ts = fields["time_spent_min"] if "time_spent_min" in fields else (
            existing["time_spent_min"] if existing else None
        )
        nt = fields["notes"] if "notes" in fields else (
            existing["notes"] if existing else None
        )
        ph = fields["attempt_phase"] if "attempt_phase" in fields else (
            existing["attempt_phase"] if existing else None
        )
        if ts in (None, "") or not (nt or "").strip():
            raise bad_request(
                "Marking a problem Accepted requires both Time Spent and Notes."
            )
        if ph not in ATTEMPT_PHASES:
            raise bad_request(
                "Marking a problem Accepted requires picking when you solved it "
                "(During Contest / Upsolve)."
            )

    row = await problems_repo.upsert_attempt(conn, problem_id, me["id"], fields)
    return row
