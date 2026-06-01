"""
Contest schemas.

  • ContestOut         — bank-listing shape: counts + assignees + tutorial paths
  • ContestWithProblems — single-contest detail: above + nested problems
  • AssignedContestOut — adds the phase rollup (my_solved / during / upsolve)

All write bodies are explicitly typed; the bank routers reject unknown fields.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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
    """Adds the viewer-scoped solved/phase rollup."""

    my_solved: int = 0
    during_count: int = 0
    upsolve_count: int = 0
    unphased_solved: int = 0


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


class ContestUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    platform: str | None = None
    contest_type: str | None = None
    contest_year: int | None = None
    url: str | None = None
    notes: str | None = None


class AddProblemToContestIn(BaseModel):
    problem_id: int = Field(ge=1)
    order_idx: int | None = None


class AssignIn(BaseModel):
    """Bank → users/teams assignment body (shared by problem-assign and
    contest-assign).  Caller must provide at least one non-empty list."""

    assigned_user_ids: list[int] = Field(default_factory=list)
    assigned_team_ids: list[int] = Field(default_factory=list)


class ContestDeleted(BaseModel):
    deleted: int


class ContestProblemRemoved(BaseModel):
    contest_id: int
    removed_problem_id: int


class AssignContestResult(BaseModel):
    contest: ContestOut
    problems_assigned: int
