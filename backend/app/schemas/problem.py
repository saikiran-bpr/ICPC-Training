"""
Problem schemas.

Tags storage note: the `problems.tags` column is `text` holding a JSON-encoded
array (legacy convention).  The `Problem.tags` field below uses a
BeforeValidator to deserialize that string into a Python list, so callers
always see `list[str]`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.schemas.user import BoolFromInt


# ---------------------------------------------------------------------------
# Tag (de)serialization
# ---------------------------------------------------------------------------

def _parse_tags(value: object) -> list[str]:
    """Accept str (JSON-encoded) | list[str] | None and normalise to list[str]."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            return [t.strip() for t in value.split(",") if t.strip()]
    return []


TagList = Annotated[list[str], BeforeValidator(_parse_tags)]


# ---------------------------------------------------------------------------
# Nested rows on a problem (assignment + per-viewer attempt)
# ---------------------------------------------------------------------------

class AssignedUserRef(BaseModel):
    id: int
    name: str
    role: str


class AssignedTeamRef(BaseModel):
    id: int
    name: str


class AttemptInline(BaseModel):
    """The viewer's own attempt — `my_attempt` field on the problem row."""

    attempt_status: str | None = None
    attempt_phase: str | None = None
    problem_faced: str | None = None
    time_spent_min: int | None = None
    notes: str | None = None
    updated_at: datetime | None = None


class TeamSummaryMember(BaseModel):
    id: int
    name: str
    role_in_team: str | None = None  # 'Member'/'Reserve', None for "direct user" rows
    attempt_status: str | None = None
    problem_faced: str | None = None
    time_spent_min: int | None = None
    notes: str | None = None
    updated_at: datetime | None = None


class TeamSummary(BaseModel):
    """Coach/Admin view — per-team breakdown rendered in the expand row."""

    team_id: int | None = None  # None when this group is "Direct user assignments"
    team_name: str
    solved: int = 0
    total: int = 0
    reserve_solved: int = 0
    reserve_total: int = 0
    members: list[TeamSummaryMember] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    url: str

    platform: str | None = None
    contest_name: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    problem_index: str | None = None

    rating: int | None = None
    difficulty: str | None = None
    topic: str | None = None
    sub_topic: str | None = None
    tags: TagList = Field(default_factory=list)

    importance: str | None = None
    suggested_role: str | None = None
    prerequisites: str | None = None
    key_idea: str | None = None
    editorial_url: str | None = None
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None

    status: str | None = "Todo"
    assigned_to: str | None = None
    created_by: int | None = None
    is_bank: BoolFromInt = False
    from_contest: BoolFromInt = False
    notes: str | None = None

    date_added: datetime | None = None
    date_updated: datetime | None = None

    # Hydrated by repository
    assigned_users: list[AssignedUserRef] = Field(default_factory=list)
    assigned_teams: list[AssignedTeamRef] = Field(default_factory=list)
    my_attempt: AttemptInline | None = None
    team_summary: list[TeamSummary] = Field(default_factory=list)


class ProblemListResponse(BaseModel):
    total: int
    count: int
    results: list[ProblemOut]


class ProblemDeleted(BaseModel):
    deleted: int


# ---------------------------------------------------------------------------
# Write bodies
# ---------------------------------------------------------------------------

class ProblemWrite(BaseModel):
    """Common write shape — used by POST (required url+platform enforced in
    router) and PUT/PATCH.  Fields not provided are left untouched on update."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    url: str | None = None
    platform: str | None = None
    contest_name: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    problem_index: str | None = None
    rating: int | None = None
    difficulty: str | None = None
    topic: str | None = None
    sub_topic: str | None = None
    # Frontend may send list OR comma-separated string; tolerant on the way in.
    tags: list[str] | str | None = None
    importance: str | None = None
    suggested_role: str | None = None
    prerequisites: str | None = None
    key_idea: str | None = None
    editorial_url: str | None = None
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None
    status: str | None = None
    assigned_to: str | None = None
    notes: str | None = None

    # Many-to-many assignments — if omitted, the existing list is preserved.
    # If passed (even as []), it REPLACES the existing list.
    assigned_user_ids: list[int] | None = None
    assigned_team_ids: list[int] | None = None


class BulkCreateIn(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class BulkCreateResult(BaseModel):
    inserted: int
    skipped: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Query params for GET /api/problems and /api/bank/problems
# ---------------------------------------------------------------------------

SortKey = Literal["name", "rating", "date_added", "importance", "id", "difficulty"]
SortOrder = Literal["asc", "desc"]


class ProblemFilters(BaseModel):
    """All query params the list endpoint accepts."""

    q: str | None = None
    platform: str | None = None
    topic: str | None = None
    difficulty: str | None = None
    importance: str | None = None
    status: str | None = None
    suggested_role: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    rating_min: int | None = None
    rating_max: int | None = None
    sort: SortKey = "date_added"
    order: SortOrder = "desc"
    limit: int | None = Field(default=None, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
