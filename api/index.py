"""
Vercel serverless entrypoint for the FastAPI backend.

Vercel's Python runtime serves any module-level `app` that is an ASGI
application, so we simply import the existing FastAPI app.  The `backend`
directory is added to `sys.path` so the `app` package (backend/app) resolves,
and `vercel.json` force-includes `backend/**` in the function bundle.

Note: FastAPI lifespan (eager DB-pool open) may not run under Vercel's ASGI
invocation — that's fine, `app.db.get_pool()` opens the pool lazily on the
first request instead.
"""

import sys
from pathlib import Path

# backend/app is the package root; put backend/ on the path.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402  (import after sys.path tweak)

# Vercel looks for a module-level `app` ASGI callable.
__all__ = ["app"]
