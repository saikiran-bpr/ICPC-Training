"""
Auth router — 5 endpoints, line-for-line port of legacy/app.py:980-1073.

All five set/clear the session cookie via `Response.set_cookie` / .delete_cookie
rather than Flask's `session[...]` magic — the cookie payload is the same
shape (`{"user_id": int}`) signed by `app/security.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.config import settings
from app.deps import ConnDep, CurrentUser, CurrentUserOptional
from app.errors import bad_request, conflict, forbidden, unauthorized
from app.repositories import users as users_repo
from app.schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    MeAnon,
    MeAuth,
    OkResponse,
    SignupIn,
    SignupResponse,
)
from app.schemas.user import UserOut
from app.security import hash_password, sign_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(resp: Response, user_id: int) -> None:
    token = sign_session({"user_id": user_id})
    resp.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_lifetime_days * 86_400,
        httponly=True,
        samesite=settings.cookie_samesite,  # "none" in prod for cross-site
        secure=settings.cookie_secure,      # True in prod (HTTPS)
        path="/",
    )


def _clear_session_cookie(resp: Response) -> None:
    # Flags must match set_cookie or the browser won't clear it.
    resp.delete_cookie(
        settings.session_cookie_name,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/signup — public; always creates a Contestant
# legacy: app.py:980-1017
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def auth_signup(payload: SignupIn, conn: ConnDep) -> SignupResponse:
    """Public signup.

    Creates a Contestant row with status='pending' (the column default).  No
    session cookie is set — the user cannot sign in until an admin approves
    the request on the /requests admin page.
    """
    email = payload.email.strip().lower()
    if await users_repo.email_exists(conn, email):
        raise conflict("An account with that email already exists")

    await users_repo.insert(
        conn,
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        role="Contestant",
        handle=(payload.handle or "").strip() or None,
        institution=(payload.institution or "").strip() or None,
        year_of_study=payload.year_of_study,
    )
    return SignupResponse(email=email)


# ---------------------------------------------------------------------------
# POST /api/auth/login
# legacy: app.py:1020-1040
# ---------------------------------------------------------------------------

@router.post("/login", response_model=UserOut)
async def auth_login(payload: LoginIn, response: Response, conn: ConnDep) -> dict:
    email = payload.email.strip().lower()
    row = await users_repo.get_by_email(conn, email)
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise unauthorized("Invalid email or password")
    if row.get("status") == "pending":
        raise forbidden(
            "Your signup request is awaiting admin approval. "
            "You'll be able to sign in once an admin reviews your account."
        )
    if row.get("status") == "rejected":
        raise forbidden("Your signup request was not approved.")
    if not row["is_active"]:
        raise forbidden("Account is deactivated")

    await users_repo.update_last_login(conn, row["id"])
    _set_session_cookie(response, row["id"])

    public = await users_repo.get_by_id(conn, row["id"])
    assert public is not None
    return public


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# legacy: app.py:1043-1046
# ---------------------------------------------------------------------------

@router.post("/logout", response_model=OkResponse)
async def auth_logout(response: Response) -> OkResponse:
    _clear_session_cookie(response)
    return OkResponse()


# ---------------------------------------------------------------------------
# GET /api/auth/me — discriminated response so the frontend handles both
# legacy: app.py:1049-1054
# ---------------------------------------------------------------------------

@router.get("/me", response_model=MeAuth | MeAnon)
async def auth_me(me: CurrentUserOptional) -> MeAuth | MeAnon:
    if me is None:
        return MeAnon()
    return MeAuth(user=UserOut.model_validate(me))


# ---------------------------------------------------------------------------
# POST /api/auth/password
# legacy: app.py:1057-1073
# ---------------------------------------------------------------------------

@router.post("/password", response_model=OkResponse)
async def auth_change_password(
    payload: ChangePasswordIn,
    me: CurrentUser,
    conn: ConnDep,
) -> OkResponse:
    full = await users_repo.get_by_email(conn, me["email"])
    if full is None:
        raise unauthorized()
    if not verify_password(payload.current_password, full["password_hash"]):
        raise unauthorized("Current password is incorrect")
    if len(payload.new_password) < 8:
        raise bad_request("New password must be at least 8 characters")
    await users_repo.update_password(conn, me["id"], hash_password(payload.new_password))
    return OkResponse()


__all__ = ["router"]
