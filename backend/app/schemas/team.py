"""
Team schemas — hydrated response (members + coaches inlined) + write bodies.

Matches legacy `serialize_team(...)` (legacy/app.py:1218-1238) so the React
frontend's TeamCard receives the same shape.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import BoolFromInt


# ---------------------------------------------------------------------------
# Nested hydrated rows
# ---------------------------------------------------------------------------

class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int                # user id
    name: str
    email: str
    handle: str | None = None
    institution: str | None = None
    role_in_team: str
    joined_at: datetime | None = None


class TeamCoachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int                # user id
    name: str
    email: str
    role: str              # 'Admin' or 'Coach'
    assigned_at: datetime | None = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    institution: str | None = None
    description: str | None = None
    is_active: BoolFromInt = True
    created_at: datetime | None = None
    created_by: int | None = None

    members: list[TeamMemberOut] = Field(default_factory=list)
    coaches: list[TeamCoachOut] = Field(default_factory=list)
    member_count: int = 0
    reserve_count: int = 0


# ---------------------------------------------------------------------------
# Write bodies
# ---------------------------------------------------------------------------

class TeamCreate(BaseModel):
    name: str = Field(min_length=1)
    institution: str | None = None
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    institution: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AddMemberIn(BaseModel):
    user_id: int = Field(ge=1)
    role_in_team: str = "Member"


class UpdateMemberIn(BaseModel):
    role_in_team: str


class AddCoachIn(BaseModel):
    user_id: int = Field(ge=1)


class DeletedResponse(BaseModel):
    """Generic shape returned by DELETE endpoints in this domain."""

    team_id: int
    removed_user_id: int


class TeamDeletedResponse(BaseModel):
    deleted: int
