"""
Schemas for /api/assignment-options — used by the React frontend's
MultiSelect widgets in ProblemModal and AssignModal.
"""

from __future__ import annotations

from pydantic import BaseModel


class AssignmentUserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str


class AssignmentTeamOut(BaseModel):
    id: int
    name: str
    institution: str | None = None


class AssignmentOptionsOut(BaseModel):
    users: list[AssignmentUserOut]
    teams: list[AssignmentTeamOut]
