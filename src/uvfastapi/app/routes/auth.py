"""
routes/auth.py

Public endpoints (no token required):
  POST /auth/register/admin   — Admin self-registration (pending superadmin approval)
  POST /auth/login            — Any role; returns access + refresh tokens

Protected endpoints:
  POST /auth/refresh          — Swap a valid refresh token for a new token pair
  POST /auth/logout           — Revoke the supplied refresh token
  GET  /auth/me               — Return the current user's profile
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from uvfastapi.app.middleware.auth import AnyAuthenticatedDep
from uvfastapi.app.models import (
    AdminRegisterRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserProfileResponse,
)
from uvfastapi.database.connection import get_pool
from uvfastapi.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


#  Admin self-registration

@router.post(
    "/register/admin",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin self-registration (requires superadmin approval before login)",
)
async def register_admin(payload: AdminRegisterRequest, request: Request):
    pool = await get_pool()
    await auth_service.register_admin(pool, payload, request)
    return MessageResponse(
        message="Admin registration received. Awaiting superadmin approval.",
        data={"email": payload.email, "username": payload.username},
    )


#  Login

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login for any role (superadmin / admin / user)",
)
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    pool = await get_pool()
    return await auth_service.authenticate(pool, payload, request)

#  Refresh

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access + refresh token pair",
)
async def refresh_tokens(payload: RefreshTokenRequest, request: Request) -> TokenResponse:
    pool = await get_pool()
    return await auth_service.rotate_refresh_token(pool, payload.refresh_token, request)

#  Logout

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the supplied refresh token (logout)",
)
async def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> MessageResponse:
    pool = await get_pool()
    await auth_service.revoke_token(pool, payload.refresh_token, current_user.id, request)
    return MessageResponse(message="Logged out successfully.")


#  Me

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Return the currently authenticated user's profile",
)
async def get_me(current_user: AnyAuthenticatedDep) -> UserProfileResponse:
    pool = await get_pool()
    return await auth_service.get_current_user_profile(pool, current_user.id)