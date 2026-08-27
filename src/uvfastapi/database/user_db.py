"""
database/user_db.py — Raw asyncpg queries for the users table.

All functions accept a connection/pool acquired from database.connection.get_pool().
No business logic lives here — callers in the service layer own that.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg


#  Helpers

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


#  Reads

async def get_user_by_id(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
) -> asyncpg.Record | None:
    """Fetch a non-deleted user by PK."""
    return await pool.fetchrow(
        """
        SELECT id, email, username, hashed_password, role,
               is_active, is_verified, created_by,
               last_login_at, created_at, updated_at, deleted_at
          FROM users
         WHERE id = $1
           AND deleted_at IS NULL
        """,
        user_id,
    )


async def get_user_by_email(
    pool: asyncpg.Pool,
    email: str,
) -> asyncpg.Record | None:
    """Fetch a non-deleted user by email (case-insensitive)."""
    return await pool.fetchrow(
        """
        SELECT id, email, username, hashed_password, role,
               is_active, is_verified, created_by,
               last_login_at, created_at, updated_at, deleted_at
          FROM users
         WHERE lower(email) = lower($1)
           AND deleted_at IS NULL
        """,
        email,
    )


async def get_user_by_username(
    pool: asyncpg.Pool,
    username: str,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        SELECT id FROM users
         WHERE lower(username) = lower($1)
           AND deleted_at IS NULL
        """,
        username,
    )


async def get_user_by_id_and_creator(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    created_by: uuid.UUID,
) -> asyncpg.Record | None:
    """
    Fetch a USER-role record that belongs to a specific admin.
    Returns None both when the user doesn't exist AND when they belong
    to a different admin (prevents info leak via 403 vs 404 distinction).
    """
    return await pool.fetchrow(
        """
        SELECT id, email, username, role,
               is_active, is_verified, created_by,
               last_login_at, created_at
          FROM users
         WHERE id         = $1
           AND created_by = $2
           AND role       = 'USER'
           AND deleted_at IS NULL
        """,
        user_id,
        created_by,
    )


async def list_users_by_creator(
    pool: asyncpg.Pool,
    created_by: uuid.UUID,
) -> list[asyncpg.Record]:
    """All non-deleted USER-role accounts under a specific admin."""
    return await pool.fetch(
        """
        SELECT id, email, username, role,
               is_active, is_verified, created_by,
               last_login_at, created_at
          FROM users
         WHERE created_by = $1
           AND role       = 'USER'
           AND deleted_at IS NULL
         ORDER BY created_at DESC
        """,
        created_by,
    )


async def list_all_users(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """Superadmin view — every non-deleted USER across all admins."""
    return await pool.fetch(
        """
        SELECT id, email, username, role,
               is_active, is_verified, created_by,
               last_login_at, created_at
          FROM users
         WHERE role       = 'USER'
           AND deleted_at IS NULL
         ORDER BY created_at DESC
        """,
    )


async def list_all_admins(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """All non-deleted ADMIN accounts (active and inactive)."""
    return await pool.fetch(
        """
        SELECT id, email, username, role,
               is_active, is_verified, created_at
          FROM users
         WHERE role       = 'ADMIN'
           AND deleted_at IS NULL
         ORDER BY created_at DESC
        """,
    )


async def list_pending_admins(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """ADMIN accounts awaiting superadmin approval (is_active = FALSE)."""
    return await pool.fetch(
        """
        SELECT id, email, username, created_at
          FROM users
         WHERE role       = 'ADMIN'
           AND is_active  = FALSE
           AND deleted_at IS NULL
         ORDER BY created_at DESC
        """,
    )


async def get_admin_by_id(
    pool: asyncpg.Pool,
    admin_id: uuid.UUID,
) -> asyncpg.Record | None:
    """Fetch a non-deleted ADMIN row by PK."""
    return await pool.fetchrow(
        """
        SELECT id, email, username, role, is_active, is_verified, created_at
          FROM users
         WHERE id         = $1
           AND role       = 'ADMIN'
           AND deleted_at IS NULL
        """,
        admin_id,
    )


#  Writes

async def create_user(
    pool: asyncpg.Pool,
    *,
    email: str,
    username: str,
    hashed_password: str,
    role: str,
    is_active: bool,
    is_verified: bool,
    created_by: uuid.UUID | None,
) -> asyncpg.Record:
    """INSERT a new user row and return the full record."""
    return await pool.fetchrow(
        """
        INSERT INTO users
               (id, email, username, hashed_password, role,
                is_active, is_verified, created_by, created_at, updated_at)
        VALUES ($1,   $2,     $3,         $4,         $5,
                $6,       $7,          $8,         NOW(),      NOW())
        RETURNING id, email, username, role,
                  is_active, is_verified, created_by, last_login_at, created_at
        """,
        uuid.uuid4(),
        email,
        username,
        hashed_password,
        role,
        is_active,
        is_verified,
        created_by,
    )


async def set_user_active(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    is_active: bool,
) -> None:
    await pool.execute(
        """
        UPDATE users
           SET is_active  = $2,
               updated_at = NOW()
         WHERE id = $1
        """,
        user_id,
        is_active,
    )


async def soft_delete_user(pool: asyncpg.Pool, user_id: uuid.UUID) -> None:
    await pool.execute(
        """
        UPDATE users
           SET deleted_at = NOW(),
               is_active  = FALSE,
               updated_at = NOW()
         WHERE id = $1
        """,
        user_id,
    )


async def update_last_login(pool: asyncpg.Pool, user_id: uuid.UUID) -> None:
    await pool.execute(
        """
        UPDATE users
           SET last_login_at = NOW(),
               updated_at    = NOW()
         WHERE id = $1
        """,
        user_id,
    )