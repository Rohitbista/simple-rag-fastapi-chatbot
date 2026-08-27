"""
database/auth_db.py — Raw asyncpg queries for refresh_tokens and audit_logs.

Refresh token contract:
  - Only the SHA-256 hex hash is stored (never the raw JWT).
  - Rotation: old token is revoked, new row is inserted in one transaction.
  - Bulk revocation: used when a user is deactivated or deleted.

Audit log contract:
  - Append-only. Rows are NEVER updated or deleted.
  - user_id is nullable (system/cron actions have no actor).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import json

import asyncpg


#  Refresh tokens

async def store_refresh_token(
    pool: asyncpg.Pool,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Persist a new (non-revoked) refresh token row."""
    await pool.execute(
        """
        INSERT INTO refresh_tokens
               (id, user_id, token_hash, expires_at,
                is_revoked, ip_address, user_agent, created_at)
        VALUES ($1,    $2,       $3,        $4,
                FALSE,     $5,         $6,         NOW())
        """,
        uuid.uuid4(),
        user_id,
        token_hash,
        expires_at,
        ip_address,
        user_agent,
    )


async def get_refresh_token(
    pool: asyncpg.Pool,
    token_hash: str,
) -> asyncpg.Record | None:
    """Look up a refresh token by its hash. Returns None if not found."""
    return await pool.fetchrow(
        """
        SELECT id, user_id, token_hash, expires_at, is_revoked, created_at
          FROM refresh_tokens
         WHERE token_hash = $1
        """,
        token_hash,
    )


async def revoke_refresh_token(
    pool: asyncpg.Pool,
    token_hash: str,
) -> None:
    """Mark a single refresh token as revoked."""
    await pool.execute(
        """
        UPDATE refresh_tokens
           SET is_revoked = TRUE
         WHERE token_hash = $1
        """,
        token_hash,
    )


async def revoke_all_user_tokens(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
) -> None:
    """
    Revoke every non-expired refresh token for a user.
    Called on deactivation, deletion, or password change.
    """
    await pool.execute(
        """
        UPDATE refresh_tokens
           SET is_revoked = TRUE
         WHERE user_id    = $1
           AND is_revoked = FALSE
           AND expires_at > NOW()
        """,
        user_id,
    )


#  Audit logs

async def insert_audit_log(
    pool: asyncpg.Pool,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Append an immutable audit event.

    action examples: "user.created", "admin.approved", "session.chat"
    """
    await pool.execute(
        """
        INSERT INTO audit_logs
               (id, user_id, action, resource_type, resource_id,
                ip_address, user_agent, details, created_at)
        VALUES ($1,    $2,     $3,        $4,           $5,
                   $6,         $7,        $8,       NOW())
        """,
        uuid.uuid4(),
        user_id,
        action,
        resource_type,
        resource_id,
        ip_address,
        user_agent,
        json.dumps(details) if details is not None else None,
    )