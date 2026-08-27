"""
services/superadmin_service.py — Business logic for SUPERADMIN-only operations.

Covers:
  - Admin lifecycle: list, list-pending, approve, deactivate, soft-delete
  - System-wide user visibility: list all users, get any user
"""

from __future__ import annotations

import uuid

import asyncpg
from fastapi import HTTPException, status

from uvfastapi.app.models import (
    AdminListResponse,
    AdminProfileResponse,
    ApproveAdminResponse,
    MessageResponse,
    PendingAdminResponse,
    UserListResponse,
    UserProfileResponse,
)
from uvfastapi.database.auth_db import insert_audit_log, revoke_all_user_tokens
from uvfastapi.database.user_db import (
    get_admin_by_id,
    get_user_by_id,
    list_all_admins,
    list_all_users,
    list_pending_admins,
    set_user_active,
    soft_delete_user,
)

ad_er="Admin not found."

#  Helpers

def _to_admin_profile(row: asyncpg.Record) -> AdminProfileResponse:
    return AdminProfileResponse(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        is_active=row["is_active"],
        is_verified=row["is_verified"],
        created_at=row["created_at"],
    )


def _to_user_profile(row: asyncpg.Record) -> UserProfileResponse:
    return UserProfileResponse(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        role=row["role"] if isinstance(row["role"], str) else row["role"].value,
        is_active=row["is_active"],
        is_verified=row["is_verified"],
        created_at=row["created_at"],
        last_login_at=row.get("last_login_at"),
    )


#  Admin listing

async def get_all_admins(pool: asyncpg.Pool) -> AdminListResponse:
    rows = await list_all_admins(pool)
    admins = [_to_admin_profile(r) for r in rows]
    return AdminListResponse(admins=admins, total=len(admins))


async def get_pending_admins(pool: asyncpg.Pool) -> list[PendingAdminResponse]:
    rows = await list_pending_admins(pool)
    return [
        PendingAdminResponse(
            id=r["id"],
            email=r["email"],
            username=r["username"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


#  Admin approval

async def approve_admin(
    pool: asyncpg.Pool,
    admin_id: uuid.UUID,
    superadmin_id: str,
) -> ApproveAdminResponse:
    """
    Approve a pending admin registration by setting is_active=TRUE.

    Raises:
      404 — admin_id not found or not an ADMIN role
      400 — admin is already active
    """
    row = await get_admin_by_id(pool, admin_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ad_er,
        )

    if row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is already active.",
        )

    await set_user_active(pool, admin_id, True)

    await insert_audit_log(
        pool,
        action="admin.approved",
        user_id=uuid.UUID(superadmin_id),
        resource_type="user",
        resource_id=admin_id,
        details={"approved_by": superadmin_id},
    )

    return ApproveAdminResponse(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        is_active=True,
        message="Admin account has been approved and is now active.",
    )


#  Admin deactivation

async def deactivate_admin(
    pool: asyncpg.Pool,
    admin_id: uuid.UUID,
    superadmin_id: str,
) -> MessageResponse:
    """
    Deactivate an active admin (blocks login without deleting).
    Revokes all active refresh tokens for the admin.

    Raises:
      404 — not found or not an ADMIN
      400 — already inactive
    """
    row = await get_admin_by_id(pool, admin_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ad_er,
        )

    if not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is already inactive.",
        )

    await set_user_active(pool, admin_id, False)
    await revoke_all_user_tokens(pool, admin_id)

    await insert_audit_log(
        pool,
        action="admin.deactivated",
        user_id=uuid.UUID(superadmin_id),
        resource_type="user",
        resource_id=admin_id,
        details={"deactivated_by": superadmin_id},
    )

    return MessageResponse(message="Admin account has been deactivated.")


#  Admin soft-delete

async def delete_admin(
    pool: asyncpg.Pool,
    admin_id: uuid.UUID,
    superadmin_id: str,
) -> MessageResponse:
    """
    Soft-delete an admin (sets deleted_at + is_active=FALSE).
    Revokes all active refresh tokens.
    """
    row = await get_admin_by_id(pool, admin_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ad_er,
        )

    await soft_delete_user(pool, admin_id)
    await revoke_all_user_tokens(pool, admin_id)

    await insert_audit_log(
        pool,
        action="admin.deleted",
        user_id=uuid.UUID(superadmin_id),
        resource_type="user",
        resource_id=admin_id,
        details={"deleted_by": superadmin_id},
    )

    return MessageResponse(message="Admin account has been deleted.")


#  System-wide user visibility

async def get_all_users(pool: asyncpg.Pool) -> UserListResponse:
    rows = await list_all_users(pool)
    users = [_to_user_profile(r) for r in rows]
    return UserListResponse(users=users, total=len(users))


async def get_user_profile(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
) -> UserProfileResponse:
    row = await get_user_by_id(pool, user_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return _to_user_profile(row)