"""
Password hashing + session cookie sign/unsign.

  • Passwords: werkzeug PBKDF2-SHA256 (compatible with hashes written by the
    legacy Flask app, so existing user rows continue to log in).
  • Sessions: signed via itsdangerous URLSafeTimedSerializer.  The cookie
    payload is just `{"user_id": int}` — no role, no name; the rest is read
    fresh from the DB on each request so role changes take effect immediately.
"""

from __future__ import annotations

import json
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash as _wz_check
from werkzeug.security import generate_password_hash as _wz_hash

from app.config import settings

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """PBKDF2-SHA256 with a 16-byte salt — matches the legacy app's format."""
    return _wz_hash(plain, method="pbkdf2:sha256", salt_length=16)


def verify_password(plain: str, hashed: str) -> bool:
    return _wz_check(hashed, plain)


# ---------------------------------------------------------------------------
# Session cookies
# ---------------------------------------------------------------------------

_serializer = URLSafeTimedSerializer(settings.flask_secret_key, salt="session")


def sign_session(payload: dict[str, Any]) -> str:
    return _serializer.dumps(json.dumps(payload, separators=(",", ":")))


def unsign_session(token: str) -> dict[str, Any] | None:
    """Return the decoded session payload, or None if invalid / expired."""
    max_age = settings.session_lifetime_days * 86_400
    try:
        raw = _serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
