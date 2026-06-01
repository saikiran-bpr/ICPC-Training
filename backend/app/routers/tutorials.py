"""
Tutorial endpoints — temporary 503 stubs.

All 7 routes from legacy/app.py:2516-2884 will eventually return real data.
For now the AI tutorial architecture is being designed separately; the
frontend's polling/generation buttons get a clear 503 instead of a confusing
404, so the UI can render a friendly "coming soon" toast.

Replace each handler with the real implementation when the design lands.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.errors import service_unavailable

router = APIRouter(tags=["tutorials"])

_DEFERRED_MSG = (
    "AI tutorials are not yet available — the worker + Socratic flow are "
    "being redesigned and will ship separately."
)


# ---------------------------------------------------------------------------
# Per-problem tutorial endpoints (5)
# ---------------------------------------------------------------------------

@router.get("/problems/{problem_id}/tutorial/status")
async def tutorial_status(
    problem_id: Annotated[int, Path(ge=1)],  # noqa: ARG001 — kept for parity
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


@router.post("/problems/{problem_id}/tutorial/unlock")
async def tutorial_unlock(
    problem_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


@router.get("/problems/{problem_id}/tutorial")
async def tutorial_html(
    problem_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


@router.get("/problems/{problem_id}/tutorial.pdf")
async def tutorial_pdf(
    problem_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


@router.post("/problems/{problem_id}/tutorial/generate")
async def tutorial_generate(
    problem_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


# ---------------------------------------------------------------------------
# Per-contest tutorial endpoints (2)
# ---------------------------------------------------------------------------

@router.get("/contests/{contest_id}/tutorial/status")
async def contest_tutorial_status(
    contest_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)


@router.post("/contests/{contest_id}/tutorial/generate")
async def contest_tutorial_generate(
    contest_id: Annotated[int, Path(ge=1)],  # noqa: ARG001
) -> dict:
    raise service_unavailable(_DEFERRED_MSG)
