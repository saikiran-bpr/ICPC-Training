"""
User schemas — request bodies + the public User response.

`UserOut` is the canonical response shape: matches what legacy/app.py
`public_user(...)` returned (legacy/app.py:460-467) so the frontend code
keeps working unchanged.  Notably:
  • `password_hash` is never exposed
  • `is_active` is coerced from smallint (0/1) to bool
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

UserRole = Literal["Admin", "Coach", "Contestant"]
USER_ROLES: tuple[UserRole, ...] = ("Admin", "Coach", "Contestant")

UserStatus = Literal["pending", "approved", "rejected"]


def _to_bool(v: object) -> bool:
    """Coerce smallint (0/1) or boolean from the DB to a Python bool."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    return bool(v)


BoolFromInt = Annotated[bool, BeforeValidator(_to_bool)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    """Public user shape returned by every endpoint that surfaces a user."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    email: str
    name: str
    role: UserRole
    handle: str | None = None
    institution: str | None = None
    year_of_study: int | None = None
    is_active: BoolFromInt = True
    status: UserStatus = "approved"
    date_joined: datetime | None = None
    last_login: datetime | None = None


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class UserSearchResponse(BaseModel):
    """Paginated response shape for GET /api/users/search."""

    total: int
    results: list[UserOut]


class UserCreate(BaseModel):
    """Admin-create: any role.  Mirrors POST /api/users (legacy 1182-1216)."""

    email: Annotated[str, Field(min_length=3)]
    password: Annotated[str, Field(min_length=8, description="At least 8 characters.")]
    name: Annotated[str, Field(min_length=1)]
    role: UserRole
    handle: str | None = None
    institution: str | None = None
    year_of_study: int | None = None


class UserUpdate(BaseModel):
    """PATCH /api/users/<uid>.  Field-level role check is enforced in the
    router (self can only update self_only fields; admin can also touch
    admin_only)."""

    # self-editable
    name: str | None = None
    handle: str | None = None
    institution: str | None = None
    year_of_study: int | None = None

    # admin-only (router validates the caller's role before honouring these)
    role: UserRole | None = None
    is_active: bool | None = None
    email: str | None = None
