#!/usr/bin/env python3
"""
Create (or promote) an admin user.  Replaces `python app.py create-admin`.

Usage:

    # Interactive (prompts for password):
    python -m backend.scripts.create_admin admin@example.com "Full Name"

    # Non-interactive (CI / scripts):
    ADMIN_PASSWORD=secretpass python -m backend.scripts.create_admin admin@example.com "Full Name"

If the user already exists, promotes them to Admin and resets their password.
Otherwise creates a fresh Admin row.
"""

from __future__ import annotations

import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path

# Allow running as both `python -m backend.scripts.create_admin` and as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.db import standalone_connection  # noqa: E402
from backend.app.security import hash_password  # noqa: E402


async def _run(email: str, name: str, password: str) -> None:
    async with standalone_connection() as conn:
        cur = await conn.execute(
            "SELECT id FROM users WHERE email = %s", (email,)
        )
        existing = await cur.fetchone()
        if existing:
            await conn.execute(
                "UPDATE users SET password_hash = %s, role = 'Admin', "
                "is_active = 1, status = 'approved' WHERE id = %s",
                (hash_password(password), existing["id"]),
            )
            await conn.commit()
            print(f"[create_admin] {email!r} already existed — promoted to Admin "
                  "and password reset.")
        else:
            # status='approved' so the admin can sign in immediately — the
            # signup-approval flow (migration 0003) defaults new rows to
            # 'pending', which would otherwise block login.
            await conn.execute(
                "INSERT INTO users (email, password_hash, name, role, status) "
                "VALUES (%s, %s, %s, 'Admin', 'approved')",
                (email, hash_password(password), name),
            )
            await conn.commit()
            print(f"[create_admin] Admin {email!r} created.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m backend.scripts.create_admin EMAIL [NAME]")
        print("       ADMIN_PASSWORD=… python -m backend.scripts.create_admin EMAIL [NAME]")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    name = sys.argv[2] if len(sys.argv) > 2 else email.split("@")[0]

    pwd = os.environ.get("ADMIN_PASSWORD")
    if not pwd:
        pwd = getpass(f"Password for {email} (min 8 chars): ")
        confirm = getpass("Confirm password: ")
        if pwd != confirm:
            print("Passwords do not match"); sys.exit(2)

    if len(pwd) < 8:
        print("Password must be at least 8 characters"); sys.exit(2)

    asyncio.run(_run(email, name, pwd))


if __name__ == "__main__":
    main()
