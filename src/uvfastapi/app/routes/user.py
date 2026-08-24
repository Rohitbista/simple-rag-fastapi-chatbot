"""
routes/user.py  —  USER-role profile endpoint.

Profile:
  GET  /api/v1/user/profile   — own profile (any authenticated role)
"""

from __future__ import annotations

from fastapi import APIRouter

from uvfastapi.app.middleware.auth import AnyAuthenticatedDep
from uvfastapi.app.models import UserProfileResponse
from uvfastapi.database.connection import get_pool
from uvfastapi.services import auth_service

router = APIRouter(
    prefix="/api/v1/user",
    tags=["User"],
)


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get own profile",
)
async def get_own_profile(current_user: AnyAuthenticatedDep) -> UserProfileResponse:
    """
    Available to any authenticated role — each user sees only their own record.
    Delegates to the same service function as /auth/me for a single source of truth.
    """
    pool = await get_pool()
    return await auth_service.get_current_user_profile(pool, current_user.id)