"""
Custom HTTP exceptions + FastAPI handlers.

FastAPI's default HTTPException already serialises to JSON; we just shape the
error body so the frontend's ApiError class (see web/src/lib/api.ts) finds the
message under `.error` — matching the legacy Flask app's response shape.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# --- shorthand raisers --------------------------------------------------------

def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def forbidden(detail: str = "Forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def not_found(detail: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def service_unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


# --- handlers -----------------------------------------------------------------

async def http_exception_handler(_req: Request, exc: HTTPException) -> JSONResponse:
    """Mirror the legacy `{"error": "..."}` body shape so the React client
    code (which reads `payload.error`) keeps working unchanged."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=getattr(exc, "headers", None) or {},
    )


async def validation_exception_handler(
    _req: Request, exc: RequestValidationError
) -> JSONResponse:
    """Turn Pydantic validation errors into the same `{"error": "..."}` shape.
    Frontend forms also do client-side validation so the user usually never
    sees these — they're a defence-in-depth."""
    errs = exc.errors()
    if errs:
        first = errs[0]
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "Invalid request")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "Invalid request"
    return JSONResponse(status_code=422, content={"error": detail})


def register_handlers(app) -> None:  # noqa: ANN001 — fastapi.FastAPI imported lazily
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
