"""
Auth schemas — login, signup, change-password, /me response.

Mirror the request shapes accepted by the legacy Flask endpoints
(legacy/app.py:980-1073).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class LoginIn(BaseModel):
    email: Annotated[str, Field(min_length=3)]
    password: Annotated[str, Field(min_length=1)]


class SignupIn(BaseModel):
    """Public signup — always creates a Contestant.  Coaches/Admins must
    be promoted by an existing admin."""

    email: Annotated[str, Field(min_length=3)]
    password: Annotated[str, Field(min_length=8)]
    name: Annotated[str, Field(min_length=1)]
    handle: str | None = None
    institution: str | None = None
    year_of_study: int | None = None


class ChangePasswordIn(BaseModel):
    current_password: Annotated[str, Field(min_length=1)]
    new_password: Annotated[str, Field(min_length=8)]


class MeAnon(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authenticated: Literal[False] = False


class MeAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authenticated: Literal[True] = True
    user: UserOut


class OkResponse(BaseModel):
    ok: bool = True


class SignupResponse(BaseModel):
    """Returned by POST /api/auth/signup.

    Signup no longer logs the user in — the account is created with
    status='pending' and waits for an admin to approve it.  The frontend uses
    `pending=True` to decide whether to redirect to the login page with an
    informational message.
    """

    pending: Literal[True] = True
    email: str
    message: str = (
        "Your signup request has been submitted and is awaiting admin approval. "
        "You'll be able to sign in once an admin reviews your account."
    )
