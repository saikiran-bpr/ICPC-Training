"""
Teams router — 11 endpoints, port of legacy/app.py:1241-1467.

Visibility / management rules carried over verbatim from the legacy app:
  • Admin sees every team unless `?mine=1`
  • Coach / Contestant: only teams they coach / belong to
  • Manage (PATCH/DELETE/members/coaches): Admin always; Coach only for
    teams they coach (`can_manage_team`)
  • DELETE team + add/remove coach: Admin-only
  • Members: only Contestants can be Member/Reserve
  • Caps: 3 Members, 1 Reserve per team
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from psycopg.errors import IntegrityError

from app.constants import (
    MAX_MEMBERS_PER_TEAM,
    MAX_RESERVES_PER_TEAM,
    TEAM_ROLES,
)
from app.deps import (
    ConnDep,
    CurrentUser,
    RequireAdmin,
    RequireCoachOrAdmin,
    can_manage_team,
    is_admin,
    is_coach_of,
    is_member_of,
)
from app.errors import bad_request, conflict, forbidden, not_found
from app.repositories import problems as problems_repo
from app.repositories import teams as teams_repo
from app.repositories import users as users_repo
from app.schemas.team import (
    AddCoachIn,
    AddMemberIn,
    DeletedResponse,
    TeamCreate,
    TeamDeletedResponse,
    TeamOut,
    TeamUpdate,
    UpdateMemberIn,
)

router = APIRouter(prefix="/teams", tags=["teams"])


# ---------------------------------------------------------------------------
# GET /api/teams
# legacy: 1241-1257
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TeamOut])
async def list_teams(
    me: CurrentUser,
    conn: ConnDep,
    mine: Annotated[bool, Query(description="If true, restrict to teams I belong to / coach.")] = False,
) -> list[dict]:
    all_teams = await teams_repo.get_all(conn)

    if is_admin(me) and not mine:
        visible = all_teams
    else:
        # One round trip resolves the user's team-id set (skill: data-n-plus-one).
        my_team_ids = await teams_repo.get_user_team_ids(conn, me["id"])
        visible = [t for t in all_teams if t["id"] in my_team_ids]

    # One members query + one coaches query for ALL visible teams (skill: N+1).
    return await teams_repo.hydrate_many(conn, visible)


# ---------------------------------------------------------------------------
# GET /api/teams/<tid>
# legacy: 1260-1270
# ---------------------------------------------------------------------------

@router.get("/{tid}", response_model=TeamOut)
async def get_team(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
) -> dict:
    row = await teams_repo.get_by_id(conn, tid)
    if row is None:
        raise not_found()
    if not is_admin(me):
        if not (await is_coach_of(conn, tid, me["id"]) or await is_member_of(conn, tid, me["id"])):
            raise forbidden()
    return await teams_repo.hydrate_one(conn, row)


# ---------------------------------------------------------------------------
# POST /api/teams
# legacy: 1273-1296
# ---------------------------------------------------------------------------

@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    me: RequireCoachOrAdmin,
    conn: ConnDep,
    payload: TeamCreate,
) -> dict:
    try:
        tid = await teams_repo.insert(
            conn,
            name=payload.name.strip(),
            institution=(payload.institution or "").strip() or None,
            description=(payload.description or "").strip() or None,
            created_by=me["id"],
        )
    except IntegrityError as e:
        raise conflict(str(e)) from e

    # Coach creator auto-becomes a coach of the new team (legacy behaviour).
    if me["role"] == "Coach":
        await teams_repo.add_coach(conn, tid, me["id"])

    row = await teams_repo.get_by_id(conn, tid)
    assert row is not None
    return await teams_repo.hydrate_one(conn, row)


# ---------------------------------------------------------------------------
# PATCH /api/teams/<tid>
# legacy: 1299-1322
# ---------------------------------------------------------------------------

@router.patch("/{tid}", response_model=TeamOut)
async def update_team(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    payload: TeamUpdate,
) -> dict:
    if not await can_manage_team(conn, tid, me):
        raise forbidden()
    if await teams_repo.get_by_id(conn, tid) is None:
        raise not_found()

    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise bad_request("No editable fields supplied")
    try:
        updated = await teams_repo.update_fields(conn, tid, fields)
    except IntegrityError as e:
        raise conflict(str(e)) from e
    if updated is None:
        raise not_found()
    return await teams_repo.hydrate_one(conn, updated)


# ---------------------------------------------------------------------------
# DELETE /api/teams/<tid>
# legacy: 1325-1333
# ---------------------------------------------------------------------------

@router.delete("/{tid}", response_model=TeamDeletedResponse)
async def delete_team(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
) -> TeamDeletedResponse:
    if await teams_repo.get_by_id(conn, tid) is None:
        raise not_found()
    if not await can_manage_team(conn, tid, me):
        raise forbidden("You can only delete teams you coach")
    if not await teams_repo.delete(conn, tid):
        raise not_found()
    return TeamDeletedResponse(deleted=tid)


# ===========================================================================
# Members
# ===========================================================================

@router.post(
    "/{tid}/members",
    response_model=TeamOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    payload: AddMemberIn,
) -> dict:
    """legacy: 1338-1378.  Enforces Member ≤ 3 + Reserve ≤ 1 caps."""
    if not await can_manage_team(conn, tid, me):
        raise forbidden()
    if payload.role_in_team not in TEAM_ROLES:
        raise bad_request(f"role_in_team must be one of {list(TEAM_ROLES)}")

    if await teams_repo.get_by_id(conn, tid) is None:
        raise not_found("Team not found")

    user = await users_repo.get_by_id(conn, payload.user_id)
    if user is None:
        raise not_found("User not found")
    if user["role"] != "Contestant":
        raise bad_request(
            "Only Contestants can be added as Member or Reserve. "
            "Use /coaches to assign coaches."
        )

    counts = await teams_repo.member_counts(conn, tid)
    if payload.role_in_team == "Member" and counts.get("Member", 0) >= MAX_MEMBERS_PER_TEAM:
        raise conflict(f"Team already has {MAX_MEMBERS_PER_TEAM} members")
    if payload.role_in_team == "Reserve" and counts.get("Reserve", 0) >= MAX_RESERVES_PER_TEAM:
        raise conflict(f"Team already has {MAX_RESERVES_PER_TEAM} reserve")

    try:
        await teams_repo.add_member(conn, tid, payload.user_id, payload.role_in_team)
    except IntegrityError as e:
        raise conflict(str(e)) from e

    row = await teams_repo.get_by_id(conn, tid)
    assert row is not None
    return await teams_repo.hydrate_one(conn, row)


@router.patch("/{tid}/members/{uid}", response_model=TeamOut)
async def update_team_member(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    uid: Annotated[int, Path(ge=1)],
    payload: UpdateMemberIn,
) -> dict:
    """legacy: 1381-1411.  Promote Reserve↔Member with cap enforcement."""
    if not await can_manage_team(conn, tid, me):
        raise forbidden()
    if payload.role_in_team not in TEAM_ROLES:
        raise bad_request(f"role_in_team must be one of {list(TEAM_ROLES)}")
    if not await teams_repo.member_exists(conn, tid, uid):
        raise not_found()

    counts = await teams_repo.member_counts(conn, tid, exclude_user=uid)
    if payload.role_in_team == "Member" and counts.get("Member", 0) >= MAX_MEMBERS_PER_TEAM:
        raise conflict(f"Team already has {MAX_MEMBERS_PER_TEAM} members")
    if payload.role_in_team == "Reserve" and counts.get("Reserve", 0) >= MAX_RESERVES_PER_TEAM:
        raise conflict(f"Team already has {MAX_RESERVES_PER_TEAM} reserve")

    await teams_repo.update_member_role(conn, tid, uid, payload.role_in_team)
    row = await teams_repo.get_by_id(conn, tid)
    assert row is not None
    return await teams_repo.hydrate_one(conn, row)


@router.delete("/{tid}/members/{uid}", response_model=DeletedResponse)
async def remove_team_member(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    uid: Annotated[int, Path(ge=1)],
) -> DeletedResponse:
    """legacy: 1414-1426."""
    if not await can_manage_team(conn, tid, me):
        raise forbidden()
    if not await teams_repo.remove_member(conn, tid, uid):
        raise not_found()
    return DeletedResponse(team_id=tid, removed_user_id=uid)


# ===========================================================================
# Coaches — Admin only
# ===========================================================================

@router.post(
    "/{tid}/coaches",
    response_model=TeamOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_coach(
    _: RequireAdmin,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    payload: AddCoachIn,
) -> dict:
    """legacy: 1431-1454."""
    if await teams_repo.get_by_id(conn, tid) is None:
        raise not_found("Team not found")
    user = await users_repo.get_by_id(conn, payload.user_id)
    if user is None:
        raise not_found("User not found")
    if user["role"] not in ("Coach", "Admin"):
        raise bad_request("Only Coach or Admin users can be assigned as a coach")

    try:
        await teams_repo.add_coach(conn, tid, payload.user_id)
    except IntegrityError as e:
        raise conflict(str(e)) from e

    row = await teams_repo.get_by_id(conn, tid)
    assert row is not None
    return await teams_repo.hydrate_one(conn, row)


@router.delete("/{tid}/coaches/{uid}", response_model=DeletedResponse)
async def remove_team_coach(
    _: RequireAdmin,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
    uid: Annotated[int, Path(ge=1)],
) -> DeletedResponse:
    """legacy: 1457-1467."""
    if not await teams_repo.remove_coach(conn, tid, uid):
        raise not_found()
    return DeletedResponse(team_id=tid, removed_user_id=uid)


# ---------------------------------------------------------------------------
# GET /api/teams/<tid>/problems
# legacy: 1470-1499
# ---------------------------------------------------------------------------

@router.get("/{tid}/problems")
async def list_team_problems(
    me: CurrentUser,
    conn: ConnDep,
    tid: Annotated[int, Path(ge=1)],
) -> dict:
    team = await teams_repo.get_by_id(conn, tid)
    if team is None:
        raise not_found()
    if me["role"] == "Coach" and not await is_coach_of(conn, tid, me["id"]):
        raise forbidden()
    if me["role"] == "Contestant" and not await is_member_of(conn, tid, me["id"]):
        raise forbidden()
    rows = await problems_repo.list_for_team(conn, tid)
    hydrated = await problems_repo.hydrate_many(conn, rows, me)
    return {
        "team": {
            "id": team["id"],
            "name": team["name"],
            "institution": team["institution"],
        },
        "count": len(hydrated),
        "results": hydrated,
    }
