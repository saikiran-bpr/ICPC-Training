"""
FastAPI app entry point.

Routers are mounted under `/api` so the React frontend's `lib/api.ts` (which
prepends `/api`) works without changes.  Static files (the legacy SPA at
`static/index.html`) are mounted at the root for backwards compatibility.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import close_pool, get_pool
from app.errors import not_found, register_handlers
from app.routers import admin as admin_router
from app.routers import assignment as assignment_router
from app.routers import auth as auth_router
from app.routers import bank as bank_router
from app.routers import contests as contests_router
from app.routers import export as export_router
from app.routers import lookup as lookup_router
from app.routers import meta as meta_router
from app.routers import problems as problems_router
from app.routers import stats as stats_router
from app.routers import teams as teams_router
from app.routers import tutorials as tutorials_router
from app.routers import users as users_router

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Open the connection pool eagerly so the first request doesn't pay
    # the connection cost.  Fails loudly if DATABASE_URL is wrong.
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="ICPC Training API",
    version="0.1.0",
    lifespan=lifespan,
)

# --- middleware ---------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- exception handlers -------------------------------------------------------

register_handlers(app)

# --- health check (used by Render's health probe) -----------------------------


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness probe.  Intentionally does NOT touch the DB so a transient
    Supabase hiccup doesn't flap the service health."""
    return {"ok": True}

# --- API routers --------------------------------------------------------------

app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")
app.include_router(users_router.router, prefix="/api")
app.include_router(teams_router.router, prefix="/api")
app.include_router(meta_router.router, prefix="/api")
app.include_router(assignment_router.router, prefix="/api")
app.include_router(problems_router.router, prefix="/api")
app.include_router(lookup_router.router, prefix="/api")
app.include_router(contests_router.router, prefix="/api")
app.include_router(bank_router.router, prefix="/api")
app.include_router(stats_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
app.include_router(tutorials_router.router, prefix="/api")


@app.get("/files/{relpath:path}")
async def serve_project_file(relpath: str) -> FileResponse:
    """Serve tutorial PDFs referenced by `contest.tutorial_pdf` /
    `tutorial_translated`.  Confined to REPO_ROOT to block `..` traversal AND
    restricted to `.pdf` files — otherwise this is an unauthenticated arbitrary
    file read (source code, .env, etc.).  This endpoint only ever serves PDFs."""
    target = (REPO_ROOT / relpath).resolve()
    try:
        target.relative_to(REPO_ROOT)
    except ValueError:
        raise not_found()
    if target.suffix.lower() != ".pdf" or not target.is_file():
        raise not_found()
    return FileResponse(target)


# Mount /static for the legacy SPA's CSS/JS assets (if any).
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
