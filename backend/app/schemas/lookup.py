"""
GET /api/lookup?url=... response shape.

Frontend's ProblemModal uses this to auto-fill name/rating/tags/etc. after
the user pastes a URL and clicks "Fetch details".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LookupOut(BaseModel):
    url: str
    name: str | None = None
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    topic: str | None = None
    sub_topic: str | None = None
    platform: str | None = None
    contest_type: str | None = None
