"""
routes/superadmin.py  —  SUPERADMIN-only endpoints.

All routes require:  role == SUPERADMIN

RAG / data:
  POST   /api/v1/superadmin/ingest                          — re-index the vector store

Admin management:
  GET    /api/v1/superadmin/admins                          — list all admins
  GET    /api/v1/superadmin/admins/pending                  — list pending (unapproved) admins
  PATCH  /api/v1/superadmin/admins/{admin_id}/approve       — approve a pending admin
  PATCH  /api/v1/superadmin/admins/{admin_id}/deactivate    — deactivate an active admin
  DELETE /api/v1/superadmin/admins/{admin_id}               — soft-delete an admin

User visibility (system-wide):
  GET    /api/v1/superadmin/users                           — list every user in the system
  GET    /api/v1/superadmin/users/{user_id}                 — a specific user's profile
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from uvfastapi.app.middleware.auth import SuperAdminDep
from uvfastapi.app.models import (
    AdminListResponse,
    ApproveAdminResponse,
    MessageResponse,
    PendingAdminResponse,
    UserListResponse,
    UserProfileResponse,
)
from uvfastapi.database.connection import get_pool
from uvfastapi.services import superadmin_service

router = APIRouter(
    prefix="/api/v1/superadmin",
    tags=["SuperAdmin"],
)


# ═════════════════════════════════════════════
#  RAG / Data ingestion
# ═════════════════════════════════════════════

@router.post(
    "/ingest",
    response_model=MessageResponse,
    summary="Re-index the vector store (superadmin only)",
)
async def ingest_data(request: Request, current_user: SuperAdminDep):
    """
    Triggers a full re-ingestion of source data into the vector store.
    The refreshed vectorstore is hot-swapped into app.state.
    """
    try:
        from uvfastapi.services.user_service import create_or_replace_vector_store
        from uvfastapi.rag_engine.orchestrator import get_vectorstore_for_retrieval

        create_or_replace_vector_store(request.app.state.embedding_function)
        request.app.state.vectorstore = get_vectorstore_for_retrieval(
            request.app.state.embedding_function
        )
        return MessageResponse(message="Vector store re-indexed successfully.")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}",
        )


# ═════════════════════════════════════════════
#  Admin management
# ═════════════════════════════════════════════

@router.get(
    "/admins",
    response_model=AdminListResponse,
    summary="List all admins (active and inactive)",
)
async def list_admins(current_user: SuperAdminDep) -> AdminListResponse:
    pool = await get_pool()
    return await superadmin_service.get_all_admins(pool)


@router.get(
    "/admins/pending",
    response_model=list[PendingAdminResponse],
    summary="List admins whose registration is pending approval",
)
async def list_pending_admins(current_user: SuperAdminDep) -> list[PendingAdminResponse]:
    pool = await get_pool()
    return await superadmin_service.get_pending_admins(pool)


@router.patch(
    "/admins/{admin_id}/approve",
    response_model=ApproveAdminResponse,
    summary="Approve a pending admin registration",
)
async def approve_admin(admin_id: uuid.UUID, current_user: SuperAdminDep) -> ApproveAdminResponse:
    pool = await get_pool()
    return await superadmin_service.approve_admin(pool, admin_id, current_user.id)


@router.patch(
    "/admins/{admin_id}/deactivate",
    response_model=MessageResponse,
    summary="Deactivate an active admin (blocks login without deleting)",
)
async def deactivate_admin(admin_id: uuid.UUID, current_user: SuperAdminDep) -> MessageResponse:
    pool = await get_pool()
    return await superadmin_service.deactivate_admin(pool, admin_id, current_user.id)


@router.delete(
    "/admins/{admin_id}",
    response_model=MessageResponse,
    summary="Soft-delete an admin account",
)
async def delete_admin(admin_id: uuid.UUID, current_user: SuperAdminDep) -> MessageResponse:
    pool = await get_pool()
    return await superadmin_service.delete_admin(pool, admin_id, current_user.id)


# ═════════════════════════════════════════════
#  User visibility (system-wide)
# ═════════════════════════════════════════════

@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List every user in the system across all admins",
)
async def list_all_users(current_user: SuperAdminDep) -> UserListResponse:
    pool = await get_pool()
    return await superadmin_service.get_all_users(pool)


@router.get(
    "/users/{user_id}",
    response_model=UserProfileResponse,
    summary="Get a specific user's profile",
)
async def get_user(user_id: uuid.UUID, current_user: SuperAdminDep) -> UserProfileResponse:
    pool = await get_pool()
    return await superadmin_service.get_user_profile(pool, user_id)