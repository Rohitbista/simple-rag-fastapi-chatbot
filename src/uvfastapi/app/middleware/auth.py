"""
middleware/auth.py — JWT creation, verification, and role-gating dependencies.

Flow:
  1.  Login  →  issue access_token (short-lived) + refresh_token (long-lived)
  2.  Every protected route depends on `get_current_user`
  3.  Role-specific routes additionally depend on
        require_superadmin / require_admin / require_admin_or_above
  4.  Refresh endpoint swaps a valid, non-revoked refresh_token for a new pair

Token payload:
  {
    "sub":   "<user_uuid>",
    "role":  "SUPERADMIN" | "ADMIN" | "USER",
    "type":  "access" | "refresh",
    "exp":   <unix timestamp>,
    "jti":   "<random uuid>"   # unique per token; used for revocation
  }

Settings expected in uvfastapi.config.settings:
  JWT_SECRET_KEY   — long random string (min 32 chars)
  JWT_ALGORITHM    — e.g. "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES   — e.g. 30
  REFRESH_TOKEN_EXPIRE_DAYS     — e.g. 7
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from uvfastapi.config.settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

#  Constants

ROLE_SUPERADMIN = "SUPERADMIN"
ROLE_ADMIN      = "ADMIN"
ROLE_USER       = "USER"

_bearer = HTTPBearer(auto_error=True)


#  Token helpers

def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    """Return a signed, short-lived JWT access token."""
    payload = {
        "sub":  user_id,
        "role": role,
        "type": "access",
        "jti":  str(uuid.uuid4()),
        "exp":  _now_utc() + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)),
        "iat":  _now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> tuple[str, str]:
    """
    Return (raw_token, sha256_hex_hash).
    Store only the hash in the DB; send the raw token to the client.
    """
    raw = jwt.encode(
        {
            "sub":  user_id,
            "role": role,
            "type": "refresh",
            "jti":  str(uuid.uuid4()),
            "exp":  _now_utc() + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS)),
            "iat":  _now_utc(),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a JWT.
    Raises HTTPException 401 on any failure.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_error

    if payload.get("type") != expected_type:
        raise credentials_error

    if not payload.get("sub"):
        raise credentials_error

    return payload


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hex digest — use to look up a refresh token in the DB."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


#  Current-user dependency

class CurrentUser:
    """Lightweight carrier injected into route handlers."""
    __slots__ = ("id", "role")

    def __init__(self, user_id: str, role: str) -> None:
        self.id   = user_id
        self.role = role


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    """
    Decode the Bearer token and return a CurrentUser.

    NOTE: This dependency does NOT hit the database.
    If you need to verify the user still exists / is still active,
    add a DB lookup inside your route or extend this dependency.
    For now the JWT payload is the source of truth between refreshes.
    """
    payload = decode_token(credentials.credentials, expected_type="access")
    return CurrentUser(user_id=payload["sub"], role=payload["role"])


#  Role-gating dependencies

async def require_superadmin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if current_user.role != ROLE_SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required.",
        )
    return current_user


async def require_admin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Exactly ADMIN role — superadmin is NOT included here."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


async def require_admin_or_above(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """ADMIN or SUPERADMIN."""
    if current_user.role not in (ROLE_ADMIN, ROLE_SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Superadmin access required.",
        )
    return current_user


async def require_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Any authenticated user regardless of role."""
    return current_user


#  Type aliases for cleaner route signatures

SuperAdminDep       = Annotated[CurrentUser, Depends(require_superadmin)]
AdminDep            = Annotated[CurrentUser, Depends(require_admin)]
AdminOrAboveDep     = Annotated[CurrentUser, Depends(require_admin_or_above)]
AnyAuthenticatedDep = Annotated[CurrentUser, Depends(require_user)]