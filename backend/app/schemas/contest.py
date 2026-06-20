"""
Contest schemas.

  • ContestOut         — bank-listing shape: counts + assignees + tutorial paths
  • ContestWithProblems — single-contest detail: above + nested problems
  • AssignedContestOut — adds the phase rollup (my_solved / during / upsolve)

All write bodies are explicitly typed; the bank routers reject unknown fields.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.problem import ProblemOut


# ---------------------------------------------------------------------------
# Nested assignee rows
# ---------------------------------------------------------------------------

class ContestAssignedUser(BaseModel):
    id: int
    name: str
    role: str


class ContestAssignedTeam(BaseModel):
    id: int
    name: str
    institution: str | None = None
    due_date: date | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ContestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    platform: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    url: str | None = None
    notes: str | None = None

    # Tutorial pointers — set by the import scripts; kept here so the React
    # ContestCard can render PDF / English-translation links.
    tutorial_pdf: str | None = None
    tutorial_translated: str | None = None
    tutorial_lang: str | None = None

    # Star ratings — Decimal in DB (numeric(3,1)); Pydantic coerces to float on dump.
    cf_stars: Decimal | float | None = None
    ucup_stars: Decimal | float | None = None

    # Coach-assigned difficulty (3/4/5) + contest length in minutes.
    stars: int | None = None
    duration_minutes: int | None = None

    created_by: int | None = None
    date_added: datetime | None = None

    # Hydrated by repository
    problem_count: int = 0
    bank_problem_count: int = 0    # legacy field name — number of problems still unassigned
    assigned_users: list[ContestAssignedUser] = Field(default_factory=list)
    assigned_teams: list[ContestAssignedTeam] = Field(default_factory=list)


class ContestWithProblems(ContestOut):
    problems: list[ProblemOut] = Field(default_factory=list)


class AssignedContestOut(ContestOut):
    """Adds the viewer-scoped solved/phase rollup + the viewer's own status."""

    my_solved: int = 0
    during_count: int = 0
    upsolve_count: int = 0
    unphased_solved: int = 0
    my_status: str | None = None
    my_solved_count: int = 0


# ---------------------------------------------------------------------------
# Write bodies
# ---------------------------------------------------------------------------

class ContestCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    platform: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    url: str | None = None
    notes: str | None = None
    stars: int | None = Field(default=None, ge=1, le=10)
    duration_minutes: int | None = Field(default=None, gt=0)


class ContestUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    platform: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    url: str | None = None
    notes: str | None = None
    stars: int | None = Field(default=None, ge=1, le=10)
    duration_minutes: int | None = Field(default=None, gt=0)


class AddProblemToContestIn(BaseModel):
    problem_id: int = Field(ge=1)
    order_idx: int | None = None


class AssignIn(BaseModel):
    """Bank → users/teams assignment body (shared by problem-assign and
    contest-assign).  Caller must provide at least one non-empty list."""

    assigned_user_ids: list[int] = Field(default_factory=list)
    assigned_team_ids: list[int] = Field(default_factory=list)


class AssignContestIn(BaseModel):
    """Contest → teams assignment body.  Teams only, with an optional deadline."""

    assigned_team_ids: list[int] = Field(default_factory=list)
    due_date: date | None = None


# ---------------------------------------------------------------------------
# Per-member contest status + reflection
# ---------------------------------------------------------------------------

MemberStatus = Literal["Not started", "Attempted", "Completed"]


class MemberEntryIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: MemberStatus = "Not started"
    solved_count: int = Field(default=0, ge=0)
    feedback: str | None = None
    mistakes: str | None = None


class MemberEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str
    status: MemberStatus
    solved_count: int = 0
    feedback: str | None = None
    mistakes: str | None = None
    updated_at: datetime | None = None


class ContestTeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    role_in_team: str | None = None
    status: MemberStatus = "Not started"
    solved_count: int = 0
    feedback: str | None = None
    mistakes: str | None = None


class ContestTeamBreakdownOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    team_name: str
    members: list[ContestTeamMemberOut] = Field(default_factory=list)


class ContestDeleted(BaseModel):
    deleted: int


class ContestProblemRemoved(BaseModel):
    contest_id: int
    removed_problem_id: int


class AssignContestResult(BaseModel):
    contest: ContestOut
    teams_assigned: int


class ContestTeamUnassigned(BaseModel):
    contest_id: int
    removed_team_id: int
