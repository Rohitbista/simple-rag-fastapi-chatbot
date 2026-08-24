"""
routes/admin.py  —  ADMIN-only endpoints.

All routes require:  role == ADMIN
An admin can only see/manage users they created (created_by == current_user.id).

User management:
  POST   /api/v1/admin/users                          — create a user under this admin
  GET    /api/v1/admin/users                          — list this admin's users
  GET    /api/v1/admin/users/{user_id}                — a specific user's profile
  PATCH  /api/v1/admin/users/{user_id}/deactivate     — deactivate a user
  DELETE /api/v1/admin/users/{user_id}                — soft-delete a user
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from uvfastapi.app.middleware.auth import AdminDep
from uvfastapi.app.models import (
    CreateUserRequest,
    MessageResponse,
    UserListResponse,
    UserProfileResponse,
)
from uvfastapi.database.connection import get_pool
from uvfastapi.services import admin_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
)


@router.post(
    "/users",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user under this admin (admin-initiated registration)",
)
async def create_user(payload: CreateUserRequest, current_user: AdminDep) -> UserProfileResponse:
    pool = await get_pool()
    return await admin_service.create_user_for_admin(pool, payload, current_user.id)


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users created by this admin",
)
async def list_my_users(current_user: AdminDep) -> UserListResponse:
    pool = await get_pool()
    return await admin_service.list_admin_users(pool, current_user.id)


@router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    summary="Get profile of a user belonging to this admin",
)
async def get_my_user(user_id: uuid.UUID, current_user: AdminDep) -> UserProfileResponse:
    pool = await get_pool()
    return await admin_service.get_admin_user(pool, user_id, current_user.id)


@router.patch(
    "/users/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Deactivate a user (blocks login without deleting)",
)
async def deactivate_user(user_id: uuid.UUID, current_user: AdminDep) -> MessageResponse:
    pool = await get_pool()
    return await admin_service.deactivate_admin_user(pool, user_id, current_user.id)


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Soft-delete a user",
)
async def delete_user(user_id: uuid.UUID, current_user: AdminDep) -> MessageResponse:
    pool = await get_pool()
    return await admin_service.delete_admin_user(pool, user_id, current_user.id)