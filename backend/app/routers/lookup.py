"""
GET /api/lookup?url=…  — URL → problem metadata for the React ProblemModal's
"Fetch details" button.  legacy/app.py:783-820.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser
from app.errors import bad_request
from app.schemas.lookup import LookupOut
from app.services import lookup as lookup_service

router = APIRouter(tags=["lookup"])


@router.get("/lookup", response_model=LookupOut)
async def lookup_problem(
    _: CurrentUser,
    url: Annotated[str, Query(min_length=1)],
) -> dict:
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise bad_request("URL must start with http:// or https://")
    return await lookup_service.lookup(url)
