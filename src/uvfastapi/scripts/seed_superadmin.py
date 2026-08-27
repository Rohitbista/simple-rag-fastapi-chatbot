"""
seed_superadmin.py — Bootstrap the first SUPERADMIN user.

Usage:
    python seed_superadmin.py
    python seed_superadmin.py --email admin@example.com --username superadmin

Reads DB credentials from the same settings module used by connection.py.
Uses a raw SQL INSERT so there is zero dependency on the ORM at seed time.
Safe to run multiple times — skips if the email or username already exists.
"""

import argparse
import getpass
import sys
import uuid

import bcrypt
from sqlalchemy import text

# Re-use the synchronous engine from connection.py
from uvfastapi.database.connection import engine



#  Helpers

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* (matches what the app expects)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def prompt_password() -> str:
    """Prompt twice and confirm the password interactively."""
    while True:
        pw = getpass.getpass("Password: ")
        if len(pw) < 8:
            print("Password must be at least 8 characters. Try again.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if pw != confirm:
            print("Passwords do not match. Try again.")
            continue
        return pw


#  Core seed logic

INSERT_SQL = text("""
    INSERT INTO users (
        id,
        email,
        username,
        hashed_password,
        role,
        is_active,
        is_verified,
        created_by,
        last_login_at,
        created_at,
        updated_at,
        deleted_at
    ) VALUES (
        :id,
        :email,
        :username,
        :hashed_password,
        'SUPERADMIN',
        TRUE,
        TRUE,
        NULL,
        NULL,
        NOW(),
        NOW(),
        NULL
    )
""")

AUDIT_SQL = text("""
    INSERT INTO audit_logs (
        id,
        user_id,
        action,
        resource_type,
        resource_id,
        ip_address,
        user_agent,
        details,
        created_at
    ) VALUES (
        :id,
        NULL,
        'user.created',
        'user',
        :resource_id,
        NULL,
        'seed_superadmin.py',
        :details,
        NOW()
    )
""")

CHECK_EMAIL_SQL    = text("SELECT id FROM users WHERE email    = :val AND deleted_at IS NULL")
CHECK_USERNAME_SQL = text("SELECT id FROM users WHERE username = :val AND deleted_at IS NULL")


def seed(email: str, username: str, password: str) -> None:
    with engine.begin() as conn:
        # ── guard: email already taken ────────────────────────
        row = conn.execute(CHECK_EMAIL_SQL, {"val": email}).fetchone()
        if row:
            print(f"[skip] A user with email '{email}' already exists (id={row[0]}).")
            sys.exit(0)

        # ── guard: username already taken ──────────────────────
        row = conn.execute(CHECK_USERNAME_SQL, {"val": username}).fetchone()
        if row:
            print(f"[skip] A user with username '{username}' already exists (id={row[0]}).")
            sys.exit(0)

        # ── insert superadmin ──────────────────────────────────
        user_id = uuid.uuid4()
        conn.execute(INSERT_SQL, {
            "id":              user_id,
            "email":           email,
            "username":        username,
            "hashed_password": hash_password(password),
        })

        # ── write audit log (actor=NULL → system/seeder) ───────
        import json
        conn.execute(AUDIT_SQL, {
            "id":          uuid.uuid4(),
            "resource_id": user_id,
            "details":     json.dumps({
                "note":     "bootstrapped via seed_superadmin.py",
                "email":    email,
                "username": username,
                "role":     "SUPERADMIN",
            }),
        })

    print(f"[ok] Superadmin created — id={user_id}  email={email}  username={username}")


#  CLI

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the initial SUPERADMIN user.")
    parser.add_argument("--email",    default="admin@example.com", help="Superadmin email")
    parser.add_argument("--username", default="superadmin",        help="Superadmin username")
    parser.add_argument("--password", default=None,
                        help="Plaintext password (omit to be prompted securely)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    password = args.password or prompt_password()
    seed(
        email=args.email,
        username=args.username,
        password=password,
    )



# How to use
# # Interactive password prompt (recommended)
# python seed_superadmin.py

# # Custom values
# python seed_superadmin.py --email me@company.com --username boss

# # Non-interactive (CI/CD, use env var to avoid shell history)
# python seed_superadmin.py --password "$SUPERADMIN_PASS"