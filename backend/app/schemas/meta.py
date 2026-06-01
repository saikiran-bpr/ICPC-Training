"""
Schemas for `GET /api/meta` — the frontend's enum/dropdown source-of-truth.
"""

from __future__ import annotations

from pydantic import BaseModel


class TeamCaps(BaseModel):
    member: int
    reserve: int


class MetaOut(BaseModel):
    platforms: list[str]
    contest_types: list[str]
    difficulties: list[str]
    topics: list[str]
    importance: list[str]
    roles: list[str]
    statuses: list[str]
    user_roles: list[str]
    team_roles: list[str]
    team_caps: TeamCaps
    attempt_statuses: list[str]
    attempt_phases: list[str]
    problem_faced: list[str]
