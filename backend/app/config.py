"""
Settings loaded from environment variables (pydantic-settings).

Fails loudly at boot if required vars are missing — replaces the silent
`os.environ.get(...) or default` pattern from the legacy Flask app.

`.env` in the repo root is read automatically for local dev.  In production
the platform's env-var panel (Render, Railway, Vercel, etc.) provides them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# /backend/app/config.py  →  parents[2] = repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---------------------------------------------------------
    database_url: str = Field(
        ...,
        description="Supabase Postgres connection URL (postgresql://...).",
    )
    # Pool sizing: Supabase free tier caps direct connections at 60.  Local
    # dev with frequent restarts can leak sockets that take ~60s to time out
    # server-side, so we deliberately stay small.  Bump in production via env.
    db_pool_min: int = Field(1, ge=1, le=50)
    db_pool_max: int = Field(5, ge=1, le=100)

    # --- Sessions ---------------------------------------------------------
    flask_secret_key: str = Field(
        ...,
        alias="FLASK_SECRET_KEY",
        description=(
            "Random hex string used to sign session cookies.  Kept under the "
            "FLASK_SECRET_KEY name for continuity with the legacy app — "
            "rotating it invalidates all existing sessions."
        ),
    )
    session_cookie_name: str = "session"
    session_lifetime_days: int = 14

    # Cookie flags.  Defaults are dev-friendly (HTTP localhost, same-site).
    # In production set COOKIE_SECURE=true and, for a cross-origin frontend
    # (e.g. a separate Render static site), COOKIE_SAMESITE=none — browsers
    # drop a SameSite=Lax cookie on cross-site requests, and SameSite=None
    # is only honoured together with Secure.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # "lax" | "strict" | "none"

    # --- CORS / Frontend --------------------------------------------------
    # NoDecode: don't let pydantic-settings JSON-parse the env value — the
    # validator below accepts both a comma-separated string and a JSON array.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",      # Vite dev server
            "http://127.0.0.1:5173",
        ],
        description=(
            "Origins allowed by CORS.  Set CORS_ORIGINS in prod — accepts a "
            "JSON array or a comma-separated string of exact origins "
            "(scheme+host, no trailing slash)."
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        # Accept either `CORS_ORIGINS=https://a.com,https://b.com` or a JSON
        # array `["https://a.com"]`.
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json

                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    # --- Server -----------------------------------------------------------
    port: int = 8000
    debug: bool = False


settings = Settings()  # type: ignore[call-arg]
