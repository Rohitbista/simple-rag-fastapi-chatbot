"""
services/admin_service.py — Business logic for ADMIN-only user management.

An admin can only see and manage users they created (created_by == admin.id).
All ownership violations surface as 404 (not 403) to prevent info leaks.
"""

from __future__ import annotations

import uuid

import asyncpg
import bcrypt
from fastapi import HTTPException, status

from uvfastapi.app.models import (
    CreateUserRequest,
    MessageResponse,
    UserListResponse,
    UserProfileResponse,
)
from uvfastapi.database.auth_db import insert_audit_log, revoke_all_user_tokens
from uvfastapi.database.user_db import (
    create_user,
    get_user_by_email,
    get_user_by_id_and_creator,
    get_user_by_username,
    list_users_by_creator,
    set_user_active,
    soft_delete_user,
)

us_er = "User not found."

#  Helpers

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _to_profile(row: asyncpg.Record) -> UserProfileResponse:
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


#  Create user

async def create_user_for_admin(
    pool: asyncpg.Pool,
    payload: CreateUserRequest,
    admin_id: str,
) -> UserProfileResponse:
    """
    Admin-initiated user registration.

    - role        = USER
    - is_active   = True
    - is_verified = True  (admin vouches)
    - created_by  = admin_id
    """
    admin_uuid = uuid.UUID(admin_id)

    # 1. Uniqueness checks
    if await get_user_by_email(pool, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    if await get_user_by_username(pool, payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken.",
        )

    # 2. Hash password
    hashed = _hash_password(payload.password)

    # 3. Insert
    user = await create_user(
        pool,
        email=payload.email,
        username=payload.username,
        hashed_password=hashed,
        role="USER",
        is_active=True,
        is_verified=True,
        created_by=admin_uuid,
    )

    # 4. Audit
    await insert_audit_log(
        pool,
        action="user.created",
        user_id=admin_uuid,
        resource_type="user",
        resource_id=user["id"],
        details={
            "email": payload.email,
            "username": payload.username,
            "created_by": admin_id,
        },
    )

    return _to_profile(user)


#  List users

async def list_admin_users(
    pool: asyncpg.Pool,
    admin_id: str,
) -> UserListResponse:
    """Return all non-deleted USER accounts created by this admin."""
    rows = await list_users_by_creator(pool, uuid.UUID(admin_id))
    users = [_to_profile(r) for r in rows]
    return UserListResponse(users=users, total=len(users))


#  Get single user

async def get_admin_user(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    admin_id: str,
) -> UserProfileResponse:
    """
    Fetch a user belonging to this admin.
    Returns 404 for both "not found" and "belongs to another admin"
    to prevent enumeration.
    """
    row = await get_user_by_id_and_creator(pool, user_id, uuid.UUID(admin_id))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=us_er,
        )
    return _to_profile(row)


#  Deactivate user

async def deactivate_admin_user(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    admin_id: str,
) -> MessageResponse:
    """
    Set is_active=FALSE and revoke all active refresh tokens.
    Ownership is verified first; 404 if not owned by this admin.
    """
    admin_uuid = uuid.UUID(admin_id)

    row = await get_user_by_id_and_creator(pool, user_id, admin_uuid)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=us_er,
        )

    # 1. Deactivate
    await set_user_active(pool, user_id, False)

    # 2. Revoke tokens
    await revoke_all_user_tokens(pool, user_id)

    # 3. Audit
    await insert_audit_log(
        pool,
        action="user.deactivated",
        user_id=admin_uuid,
        resource_type="user",
        resource_id=user_id,
        details={"deactivated_by": admin_id},
    )

    return MessageResponse(message="User has been deactivated.")


#  Soft-delete user

async def delete_admin_user(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
    admin_id: str,
) -> MessageResponse:
    """
    Soft-delete a user (sets deleted_at + is_active=FALSE) and revoke tokens.
    Only the owning admin can delete their own users.
    """
    admin_uuid = uuid.UUID(admin_id)

    row = await get_user_by_id_and_creator(pool, user_id, admin_uuid)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=us_er,
        )

    # 1. Soft delete (also sets is_active=FALSE)
    await soft_delete_user(pool, user_id)

    # 2. Revoke tokens
    await revoke_all_user_tokens(pool, user_id)

    # 3. Audit
    await insert_audit_log(
        pool,
        action="user.deleted",
        user_id=admin_uuid,
        resource_type="user",
        resource_id=user_id,
        details={"deleted_by": admin_id},
    )

    return MessageResponse(message="User has been deleted.")