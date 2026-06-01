"""
GET /api/assignment-options — picker data for the React MultiSelect widgets
in ProblemModal and AssignModal.  Admin/Coach only.

legacy/app.py:827-849.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.db import fetch_all
from app.deps import ConnDep, RequireCoachOrAdmin
from app.schemas.assignment import AssignmentOptionsOut

router = APIRouter(tags=["assignment"])


@router.get("/assignment-options", response_model=AssignmentOptionsOut)
async def assignment_options(
    _: RequireCoachOrAdmin,
    conn: ConnDep,
) -> dict:
    users = await fetch_all(
        conn,
        "SELECT id, name, email, role FROM users "
        "WHERE is_active = 1 ORDER BY name",
    )
    teams = await fetch_all(
        conn,
        "SELECT id, name, institution FROM teams "
        "WHERE is_active = 1 ORDER BY name",
    )
    return {"users": users, "teams": teams}
