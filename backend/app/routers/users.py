"""
Users router — 4 endpoints, line-for-line port of legacy/app.py:1080-1216.

Visibility rules:
  • Admin: sees every user
  • Coach: sees Admins/Coaches + Contestants on teams they coach
           (skill: data-n-plus-one — resolved in one SQL query)
  • Contestant: sees only themselves
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from psycopg.errors import IntegrityError

from app.db import fetch_one
from app.deps import ConnDep, CurrentUser, RequireAdmin, RequireCoachOrAdmin
from app.errors import bad_request, conflict, forbidden, not_found
from app.repositories import problems as problems_repo
from app.repositories import users as users_repo
from app.schemas.user import UserCreate, UserOut, UserSearchResponse, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# GET /api/users/search — paginated picker used by the team member picker.
# Coach+Admin only.  Registered BEFORE /{uid} so FastAPI matches "/search"
# as a literal, not as a uid path param.
# ---------------------------------------------------------------------------

@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    _: RequireCoachOrAdmin,
    conn: ConnDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query()] = None,
    exclude_team_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    total, rows = await users_repo.search_users(
        conn,
        q=q,
        role=role,
        exclude_team_id=exclude_team_id,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "results": rows}


# ---------------------------------------------------------------------------
# GET /api/users
# legacy: app.py:1080-1122
# ---------------------------------------------------------------------------

@router.get("", response_model=list[UserOut])
async def list_users(
    _: RequireAdmin,
    conn: ConnDep,
    role: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """Admin-only.  Coaches and Contestants cannot see the user directory."""
    return await users_repo.list_all(conn, role=role, q=q)


# ---------------------------------------------------------------------------
# GET /api/users/<uid>
# legacy: app.py:1125-1134
# ---------------------------------------------------------------------------

@router.get("/{uid}", response_model=UserOut)
async def get_user(
    me: CurrentUser,
    conn: ConnDep,
    uid: Annotated[int, Path(ge=1)],
) -> dict:
    if me["role"] != "Admin" and me["role"] != "Coach" and me["id"] != uid:
        raise forbidden()
    row = await users_repo.get_by_id(conn, uid)
    if row is None:
        raise not_found()
    return row


# ---------------------------------------------------------------------------
# PATCH /api/users/<uid>
# legacy: app.py:1137-1179
# ---------------------------------------------------------------------------

_SELF_FIELDS = {"name", "handle", "institution", "year_of_study"}
_ADMIN_FIELDS = {"role", "is_active", "email"}


@router.patch("/{uid}", response_model=UserOut)
async def update_user(
    me: CurrentUser,
    conn: ConnDep,
    uid: Annotated[int, Path(ge=1)],
    payload: UserUpdate,
) -> dict:
    if me["id"] != uid and me["role"] != "Admin":
        raise forbidden()

    raw = payload.model_dump(exclude_unset=True)
    fields: dict = {}
    for key, value in raw.items():
        if key in _SELF_FIELDS:
            fields[key] = value
        elif key in _ADMIN_FIELDS and me["role"] == "Admin":
            if key == "email" and isinstance(value, str):
                value = value.strip().lower()
            fields[key] = value
        # silently drop everything else (mirrors legacy behaviour)

    if not fields:
        raise bad_request("No editable fields supplied")

    try:
        updated = await users_repo.update_fields(conn, uid, fields)
    except IntegrityError as e:
        raise conflict(str(e)) from e
    if updated is None:
        raise not_found()
    return updated


# ---------------------------------------------------------------------------
# POST /api/users  — Admin-only
# legacy: app.py:1182-1216
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[],  # role check is via the RequireAdmin annotated dep below
)
async def admin_create_user(
    _: RequireAdmin,
    conn: ConnDep,
    payload: UserCreate,
) -> dict:
    email = payload.email.strip().lower()
    if await users_repo.email_exists(conn, email):
        raise conflict("An account with that email already exists")

    uid = await users_repo.insert(
        conn,
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        role=payload.role,
        handle=(payload.handle or "").strip() or None,
        institution=(payload.institution or "").strip() or None,
        year_of_study=payload.year_of_study,
    )
    row = await users_repo.get_by_id(conn, uid)
    assert row is not None
    return row


# ---------------------------------------------------------------------------
# GET /api/users/<uid>/problems
# legacy: app.py:1502-1560
# ---------------------------------------------------------------------------

@router.get("/{uid}/problems")
async def list_user_problems(
    me: CurrentUser,
    conn: ConnDep,
    uid: Annotated[int, Path(ge=1)],
) -> dict:
    target = await fetch_one(
        conn,
        "SELECT id, name, email, role FROM users WHERE id = %s",
        (uid,),
    )
    if target is None:
        raise not_found()

    # Permission: self, Admin, or Coach of any team this user belongs to.
    if me["id"] != uid and me["role"] != "Admin":
        if me["role"] == "Coach":
            shared = await fetch_one(
                conn,
                "SELECT 1 FROM team_members tm "
                "JOIN team_coaches tc ON tc.team_id = tm.team_id "
                "WHERE tm.user_id = %s AND tc.user_id = %s LIMIT 1",
                (uid, me["id"]),
            )
            if shared is None:
                raise forbidden()
        else:
            raise forbidden()

    rows = await problems_repo.list_for_user(conn, uid)
    hydrated = await problems_repo.hydrate_many(conn, rows, me)

    # Augment each row with the TARGET user's own attempt status (matches
    # legacy: front-end uses this to show how the user is doing).
    if rows:
        pids = [r["id"] for r in rows]
        from app.db import fetch_all
        target_attempts_rows = await fetch_all(
            conn,
            """
            SELECT problem_id, attempt_status, attempt_phase, problem_faced,
                   time_spent_min, notes, updated_at
            FROM problem_attempts
            WHERE user_id = %s AND problem_id = ANY(%s)
            """,
            (uid, pids),
        )
        target_by_pid = {
            r["problem_id"]: {
                "attempt_status": r["attempt_status"],
                "attempt_phase": r["attempt_phase"],
                "problem_faced": r["problem_faced"],
                "time_spent_min": r["time_spent_min"],
                "notes": r["notes"],
                "updated_at": r["updated_at"],
            }
            for r in target_attempts_rows
        }
        for h in hydrated:
            h["user_attempt"] = target_by_pid.get(h["id"])
    return {"user": target, "count": len(hydrated), "results": hydrated}
