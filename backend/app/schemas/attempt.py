"""
Attempt schemas — PUT /api/problems/{id}/attempt + the inline shape returned
from list endpoints.

Business rule (server-enforced, mirrors legacy/app.py:923-942):
  • If `attempt_status` is set to "Accepted", the row MUST also have
    time_spent_min, notes, and attempt_phase (provided in this call OR
    already present on the stored row).  The router resolves this with the
    existing row in hand.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttemptIn(BaseModel):
    """Partial upsert — every field is optional; the router merges with the
    existing row before validating the "Accepted needs full triple" rule."""

    model_config = ConfigDict(extra="ignore")

    attempt_status: str | None = None
    attempt_phase: str | None = None
    problem_faced: str | None = None
    time_spent_min: int | None = None
    notes: str | None = None


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_status: str | None = None
    attempt_phase: str | None = None
    problem_faced: str | None = None
    time_spent_min: int | None = None
    notes: str | None = None
    updated_at: datetime | None = None
