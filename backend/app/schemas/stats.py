"""
GET /api/stats response shape.  Each `by_*` is `[{"key": str, "n": int}, ...]`
in descending count order — what the frontend's dashboard already consumes.
"""

from __future__ import annotations

from pydantic import BaseModel


class GroupCount(BaseModel):
    key: str
    n: int


class StatsOut(BaseModel):
    total: int
    by_platform: list[GroupCount]
    by_topic: list[GroupCount]
    by_difficulty: list[GroupCount]
    by_importance: list[GroupCount]
    by_status: list[GroupCount]
