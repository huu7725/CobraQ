"""
Seed the first admin account from environment variables.

Why this exists
---------------
The signup UI only exposes "student" and "teacher" roles — there is no
self-service way to create an admin via the browser. Combined with the
fact that every Render free-tier redeploy wipes the JSON user store,
admins would otherwise vanish on each restart. Even with a persistent
disk, having to redeploy just to create the first admin is awkward.

This script reads `ADMIN_EMAIL` and `ADMIN_PASSWORD` from the
environment on every startup. If a user with that email already exists
with role=admin, it does nothing. Otherwise it:

  1. Creates the user in the JSON store (the source of truth used by
     `user_store`).
  2. Mirrors the user into the SQLite/Postgres `User` table so foreign
     keys for map progress still work.

Set these two env vars on Render → Environment → and the first admin
will appear automatically. Re-deploying with a different password will
update the existing admin's hash.

Security notes
--------------
- The script is idempotent — running it twice does nothing harmful.
- It never logs the plaintext password.
- It refuses to run if ADMIN_EMAIL / ADMIN_PASSWORD is missing.
- If ADMIN_EMAIL looks like a non-email (no '@'), it skips silently to
  avoid breaking local dev where these vars are intentionally absent.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional


def _looks_like_email(s: str) -> bool:
    return bool(s) and bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s))


def seed_admin() -> Optional[str]:
    """
    Create or refresh the admin user from ADMIN_EMAIL / ADMIN_PASSWORD.

    Returns the admin email if action was taken (created or password
    rotated), or None if the env vars are unset / invalid.
    """
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    name = (os.environ.get("ADMIN_NAME") or "Admin").strip() or "Admin"

    if not email or not password:
        return None
    if not _looks_like_email(email):
        print("[seed_admin] ADMIN_EMAIL invalid, skipping", flush=True)
        return None
    if len(password) < 8:
        print(
            "[seed_admin] ADMIN_PASSWORD too short (min 8 chars), skipping",
            flush=True,
        )
        return None

    # Import here so this module can be imported without pulling in the
    # whole FastAPI app (useful for unit tests / one-off CLI runs).
    from ..core.security import hash_password, verify_password
    from ..db.user_store import user_store

    existing = user_store.get_user(email)
    action: Optional[str] = None

    if existing:
        # Promote to admin if not already; refresh password hash if it
        # changed in the environment. Never log the plaintext password.
        updates = {}
        if existing.get("role") != "admin":
            updates["role"] = "admin"
            action = "promoted"
        try:
            if not verify_password(password, existing.get("password_hash", "")):
                updates["password_hash"] = hash_password(password)
                action = "password_rotated" if not action else action + "+password_rotated"
        except Exception:
            updates["password_hash"] = hash_password(password)
            action = "password_rotated" if not action else action + "+password_rotated"
        if updates:
            user_store.update_user(email, updates)
    else:
        user_store.create_user(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role="admin",
        )
        action = "created"

    # Mirror to the SQL `users` table so map progress / foreign keys work.
    try:
        from ..db.database import get_db
        from ..models.user import User as UserModel

        db = next(get_db())
        row = db.query(UserModel).filter(UserModel.email == email).first()
        pw_hash = (
            user_store.get_user(email).get("password_hash")
            if user_store.get_user(email)
            else hash_password(password)
        )
        if row:
            row.role = "admin"
            row.name = name
            row.password_hash = pw_hash
        else:
            db.add(
                UserModel(
                    email=email,
                    name=name,
                    password_hash=pw_hash,
                    role="admin",
                )
            )
        db.commit()
    except Exception as e:  # non-fatal: JSON store is the source of truth
        print(f"[seed_admin] mirror to SQL failed: {e}", flush=True)

    print(f"[seed_admin] admin ready: {email} ({action})", flush=True)
    return email if action else None


if __name__ == "__main__":
    # Allow running standalone: `python -m app.services.seed_admin`
    sys.exit(0 if seed_admin() is not None or True else 1)
