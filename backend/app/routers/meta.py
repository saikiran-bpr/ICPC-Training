"""
GET /api/meta — enum values for the frontend's dropdowns + role checks.

Pure constant payload, no auth required.  legacy/app.py:501-517.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.constants import (
    ATTEMPT_PHASES,
    ATTEMPT_STATUSES,
    CONTEST_TYPES,
    DIFFICULTIES,
    IMPORTANCE_LEVELS,
    MAX_MEMBERS_PER_TEAM,
    MAX_RESERVES_PER_TEAM,
    PLATFORMS,
    PROBLEM_FACED,
    ROLES_SUGGESTED,
    STATUSES,
    TEAM_ROLES,
    TOPICS,
    USER_ROLES,
)
from app.schemas.meta import MetaOut, TeamCaps

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaOut)
async def meta() -> MetaOut:
    return MetaOut(
        platforms=list(PLATFORMS),
        contest_types=list(CONTEST_TYPES),
        difficulties=list(DIFFICULTIES),
        topics=list(TOPICS),
        importance=list(IMPORTANCE_LEVELS),
        roles=list(ROLES_SUGGESTED),
        statuses=list(STATUSES),
        user_roles=list(USER_ROLES),
        team_roles=list(TEAM_ROLES),
        team_caps=TeamCaps(member=MAX_MEMBERS_PER_TEAM, reserve=MAX_RESERVES_PER_TEAM),
        attempt_statuses=list(ATTEMPT_STATUSES),
        attempt_phases=list(ATTEMPT_PHASES),
        problem_faced=list(PROBLEM_FACED),
    )
