"""
services/auth_service.py — Business logic for authentication flows.

Responsibilities:
  register_admin   — self-registration, pending superadmin approval
  authenticate     — verify credentials, issue token pair
  rotate_tokens    — refresh-token rotation (revoke old, issue new)
  revoke_token     — single-token logout
  get_current_user_profile — DB-backed /me lookup
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import bcrypt
from fastapi import HTTPException, Request, status

from uvfastapi.app.middleware.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from uvfastapi.app.models import (
    AdminRegisterRequest,
    LoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from uvfastapi.config.settings import REFRESH_TOKEN_EXPIRE_DAYS
from uvfastapi.database.auth_db import (
    get_refresh_token,
    insert_audit_log,
    revoke_refresh_token,
    store_refresh_token,
)
from uvfastapi.database.user_db import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    update_last_login,
)


#  Helpers

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_client_meta(request: Request) -> tuple[str | None, str | None]:
    """Extract IP and User-Agent from the request for audit/token storage."""
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    ua = request.headers.get("User-Agent")
    return ip, ua


#  Public: Admin self-registration

async def register_admin(
    pool: asyncpg.Pool,
    payload: AdminRegisterRequest,
    request: Request,
) -> None:
    """
    Create an ADMIN account with is_active=False (pending approval).
    Raises 409 if email or username is already taken.
    """
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

    # 3. Insert user
    user = await create_user(
        pool,
        email=payload.email,
        username=payload.username,
        hashed_password=hashed,
        role="ADMIN",
        is_active=False,    # cannot log in until approved
        is_verified=False,
        created_by=None,
    )

    # 4. Audit
    ip, ua = _get_client_meta(request)
    await insert_audit_log(
        pool,
        action="admin.registered",
        user_id=user["id"],
        resource_type="user",
        resource_id=user["id"],
        ip_address=ip,
        user_agent=ua,
        details={"email": payload.email, "username": payload.username},
    )


#  Public: Login

async def authenticate(
    pool: asyncpg.Pool,
    payload: LoginRequest,
    request: Request,
) -> TokenResponse:
    """
    Verify credentials and return a token pair.

    Error responses are deliberately non-specific to prevent user enumeration:
      - Unknown email     → 401
      - Wrong password    → 401
      - Inactive account  → 403 (pending admin, deactivated user)
    """
    ip, ua = _get_client_meta(request)

    # 1. Fetch user
    user = await get_user_by_email(pool, payload.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    # 2. Active gate (catches pending admins and deactivated accounts)
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active. Contact your administrator.",
        )

    # 3. Password check
    if not _verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    user_id_str = str(user["id"])
    role = user["role"] if isinstance(user["role"], str) else user["role"].value

    # 4. Issue tokens
    access_token = create_access_token(user_id_str, role)
    raw_refresh, refresh_hash = create_refresh_token(user_id_str, role)

    # 5. Persist refresh token
    expires_at = _now() + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
    await store_refresh_token(
        pool,
        user_id=user["id"],
        token_hash=refresh_hash,
        expires_at=expires_at,
        ip_address=ip,
        user_agent=ua,
    )

    # 6. Update last_login_at
    await update_last_login(pool, user["id"])

    # 7. Audit
    await insert_audit_log(
        pool,
        action="user.login",
        user_id=user["id"],
        resource_type="user",
        resource_id=user["id"],
        ip_address=ip,
        user_agent=ua,
    )

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


#  Protected: Token rotation

async def rotate_refresh_token(
    pool: asyncpg.Pool,
    raw_token: str,
    request: Request,
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh pair.
    The incoming token is revoked atomically before the new pair is issued.
    """
    ip, ua = _get_client_meta(request)

    # 1. Decode (raises 401 if expired or malformed)
    payload_data = decode_token(raw_token, expected_type="refresh")

    # 2. Look up hash in DB
    token_hash = hash_refresh_token(raw_token)
    row = await get_refresh_token(pool, token_hash)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    if row["is_revoked"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked.",
        )

    if row["expires_at"] < _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )

    user_id = payload_data["sub"]
    role = payload_data["role"]

    # 3. Revoke the old token
    await revoke_refresh_token(pool, token_hash)

    # 4. Issue new pair
    new_access = create_access_token(user_id, role)
    new_raw_refresh, new_hash = create_refresh_token(user_id, role)

    expires_at = _now() + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
    await store_refresh_token(
        pool,
        user_id=uuid.UUID(user_id),
        token_hash=new_hash,
        expires_at=expires_at,
        ip_address=ip,
        user_agent=ua,
    )

    return TokenResponse(access_token=new_access, refresh_token=new_raw_refresh)


#  Protected: Logout

async def revoke_token(
    pool: asyncpg.Pool,
    raw_token: str,
    current_user_id: str,
    request: Request,
) -> None:
    """
    Revoke a single refresh token, verifying it belongs to the caller.
    Silent no-op if the token is already revoked (idempotent logout).
    """
    ip, ua = _get_client_meta(request)
    token_hash = hash_refresh_token(raw_token)
    row = await get_refresh_token(pool, token_hash)

    if row and str(row["user_id"]) != current_user_id:
        # Token belongs to a different user — deny silently (no info leak)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to revoke this token.",
        )

    if row and not row["is_revoked"]:
        await revoke_refresh_token(pool, token_hash)

    await insert_audit_log(
        pool,
        action="user.logout",
        user_id=uuid.UUID(current_user_id),
        resource_type="user",
        resource_id=uuid.UUID(current_user_id),
        ip_address=ip,
        user_agent=ua,
    )


#  Protected: /me

async def get_current_user_profile(
    pool: asyncpg.Pool,
    current_user_id: str,
) -> UserProfileResponse:
    """DB-backed profile lookup for the /auth/me endpoint."""
    user = await get_user_by_id(pool, uuid.UUID(current_user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserProfileResponse(
        id=user["id"],
        email=user["email"],
        username=user["username"],
        role=user["role"] if isinstance(user["role"], str) else user["role"].value,
        is_active=user["is_active"],
        is_verified=user["is_verified"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
    )