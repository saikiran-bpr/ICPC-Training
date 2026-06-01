"""
FastAPI dependencies: current_user, role gating, team-permission helpers.

These replace the Flask decorators (`@login_required`, `@role_required`,
`current_user()`, `is_admin()`, `can_manage_team()`) line-for-line.

Usage:

    from app.deps import CurrentUser, RequireAdmin, RequireCoachOrAdmin

    @router.get("/users")
    async def list_users(me: CurrentUser, conn: ConnDep):
        ...

    @router.post("/users")
    async def create_user(_: RequireAdmin, conn: ConnDep, ...):
        ...
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Cookie, Depends
from psycopg import AsyncConnection

from app.config import settings
from app.db import fetch_one, tx
from app.errors import forbidden, unauthorized
from app.security import unsign_session

# Re-usable connection alias so handlers stay short.
ConnDep = Annotated[AsyncConnection, Depends(tx)]


# ---------------------------------------------------------------------------
# current_user
# ---------------------------------------------------------------------------

async def _resolve_user(token: str | None, conn: AsyncConnection) -> dict[str, Any] | None:
    """Decode session → fetch user row.  None if anon or stale session."""
    if not token:
        return None
    payload = unsign_session(token)
    if not payload or not isinstance(payload, dict):
        return None
    uid = payload.get("user_id")
    if not isinstance(uid, int):
        return None
    return await fetch_one(
        conn,
        "SELECT * FROM users WHERE id = %s AND is_active = 1",
        (uid,),
    )


async def current_user_optional(
    conn: ConnDep,
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> dict[str, Any] | None:
    """Returns the logged-in user dict, or None for anonymous requests."""
    return await _resolve_user(session, conn)


async def current_user(
    user: Annotated[dict[str, Any] | None, Depends(current_user_optional)],
) -> dict[str, Any]:
    """Require a logged-in user. 401 otherwise."""
    if user is None:
        raise unauthorized()
    return user


CurrentUserOptional = Annotated[dict[str, Any] | None, Depends(current_user_optional)]
CurrentUser = Annotated[dict[str, Any], Depends(current_user)]


# ---------------------------------------------------------------------------
# Role gating
# ---------------------------------------------------------------------------

def require_role(*allowed: str):
    """Build a dependency that 403s unless current_user.role is in `allowed`.
    Returns the user dict on success so the handler can `Depends()` either
    `current_user` or the role-gated variant — both yield the row."""
    async def dep(me: CurrentUser) -> dict[str, Any]:
        if me["role"] not in allowed:
            raise forbidden(f"Requires role: {', '.join(allowed)}")
        return me
    return dep


RequireAdmin = Annotated[dict[str, Any], Depends(require_role("Admin"))]
RequireCoachOrAdmin = Annotated[dict[str, Any], Depends(require_role("Admin", "Coach"))]


# ---------------------------------------------------------------------------
# Permission helpers (called inside handlers, not as deps)
# ---------------------------------------------------------------------------

def is_admin(user: dict[str, Any]) -> bool:
    return user["role"] == "Admin"


async def is_coach_of(conn: AsyncConnection, team_id: int, user_id: int) -> bool:
    row = await fetch_one(
        conn,
        "SELECT 1 FROM team_coaches WHERE team_id = %s AND user_id = %s",
        (team_id, user_id),
    )
    return row is not None


async def is_member_of(conn: AsyncConnection, team_id: int, user_id: int) -> bool:
    row = await fetch_one(
        conn,
        "SELECT 1 FROM team_members WHERE team_id = %s AND user_id = %s",
        (team_id, user_id),
    )
    return row is not None


async def can_manage_team(
    conn: AsyncConnection, team_id: int, user: dict[str, Any]
) -> bool:
    """Admins manage every team; coaches manage teams they coach."""
    if is_admin(user):
        return True
    if user["role"] == "Coach":
        return await is_coach_of(conn, team_id, user["id"])
    return False


async def can_manage_problem(
    conn: AsyncConnection, problem_id: int, user: dict[str, Any]
) -> bool:
    """Admins can edit/delete any problem; coaches only their own creations.

    `created_by` is set server-side on insert (see problems repo / routers) so
    a coach cannot impersonate ownership.  Contestants never manage problems.
    """
    if is_admin(user):
        return True
    if user["role"] != "Coach":
        return False
    row = await fetch_one(
        conn,
        "SELECT created_by FROM problems WHERE id = %s",
        (problem_id,),
    )
    return row is not None and row["created_by"] == user["id"]
