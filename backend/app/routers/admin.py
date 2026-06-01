"""
Admin-only endpoints — signup approval queue.

Routes:
  GET    /api/admin/requests        list pending signup requests
  GET    /api/admin/requests/count  count for the nav badge
  POST   /api/admin/requests/{uid}/approve   flip status='approved'
  POST   /api/admin/requests/{uid}/reject    delete the user row
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.deps import ConnDep, RequireAdmin
from app.errors import bad_request, not_found
from app.repositories import users as users_repo
from app.schemas.auth import OkResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/requests", response_model=list[UserOut])
async def list_pending_requests(_: RequireAdmin, conn: ConnDep) -> list[dict]:
    return await users_repo.list_pending(conn)


@router.get("/requests/count")
async def pending_count(_: RequireAdmin, conn: ConnDep) -> dict[str, int]:
    return {"count": await users_repo.count_pending(conn)}


@router.post("/requests/{uid}/approve", response_model=UserOut)
async def approve_request(
    _: RequireAdmin,
    conn: ConnDep,
    uid: Annotated[int, Path(ge=1)],
) -> dict:
    row = await users_repo.get_by_id(conn, uid)
    if row is None:
        raise not_found("Signup request not found")
    if row["status"] != "pending":
        raise bad_request(f"Request is already {row['status']}")
    await users_repo.set_status(conn, uid, "approved")
    updated = await users_repo.get_by_id(conn, uid)
    assert updated is not None
    return updated


@router.post("/requests/{uid}/reject", response_model=OkResponse)
async def reject_request(
    _: RequireAdmin,
    conn: ConnDep,
    uid: Annotated[int, Path(ge=1)],
) -> OkResponse:
    row = await users_repo.get_by_id(conn, uid)
    if row is None:
        raise not_found("Signup request not found")
    if row["status"] != "pending":
        raise bad_request(f"Request is already {row['status']}")
    await users_repo.delete_by_id(conn, uid)
    return OkResponse()


__all__ = ["router"]
