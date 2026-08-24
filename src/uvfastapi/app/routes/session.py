"""
routes/session.py — All chat & session endpoints, unified across roles.

Every route uses `AnyAuthenticatedDep` for auth, then branches on
`current_user.role` where access rules differ.

Role access matrix:
┌─────────────────────────────────────────────────┬────────────┬───────┬──────┐
│ Endpoint                                        │ SUPERADMIN │ ADMIN │ USER │
├─────────────────────────────────────────────────┼────────────┼───────┼──────┤
│ POST   /api/v1/session/chat                     │     ✓      │   ✓   │  ✓   │
│ DELETE /api/v1/session                          │     ✓      │   ✓   │  ✓   │
│ GET    /api/v1/session/conversations            │     ✓      │   ✓   │  ✓   │
│ GET    /api/v1/session/conversations/{conv_id}  │     ✓      │   ✓   │  ✓   │
│ POST   /api/v1/session/chat/{target_user_id}    │     ✓      │   ✓   │  ✗   │
│ DELETE /api/v1/session/{target_user_id}         │     ✓      │   ✓   │  ✗   │
│ GET    /api/v1/session/{target}/conversations   │     ✓      │   ✓   │  ✗   │
│ GET    /api/v1/session/{target}/conv/{conv_id}  │     ✓      │   ✓   │  ✗   │
└─────────────────────────────────────────────────┴────────────┴───────┴──────┘
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from uvfastapi.app.middleware.auth import AnyAuthenticatedDep
from uvfastapi.app.models import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    MessageResponse,
    UserConversationsResponse,
)
from uvfastapi.database.connection import get_pool
from uvfastapi.services import session_service

router = APIRouter(
    prefix="/api/v1/session",
    tags=["Session"],
)

ROLE_USER = "USER"


def _block_users(current_user: AnyAuthenticatedDep) -> None:
    """Raise 403 if the caller is a plain USER."""
    if current_user.role == ROLE_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Superadmin access required to interact with other users' sessions.",
        )


# ═════════════════════════════════════════════
#  Own session — available to every role
# ═════════════════════════════════════════════

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message in your own session and receive an LLM reply",
)
async def chat_own(
    payload: ChatRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> ChatResponse:
    pool = await get_pool()
    return await session_service.chat_own(pool, request, payload, current_user.id)


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear your own in-memory session (start a fresh conversation)",
)
async def clear_own_session(
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> MessageResponse:
    pool = await get_pool()
    return await session_service.clear_own_session(pool, request, current_user.id)


@router.get(
    "/conversations",
    response_model=UserConversationsResponse,
    summary="List your own persisted conversations",
)
async def list_own_conversations(current_user: AnyAuthenticatedDep) -> UserConversationsResponse:
    pool = await get_pool()
    return await session_service.list_own_conversations(pool, current_user.id)


@router.get(
    "/conversations/{conv_id}",
    response_model=ConversationHistoryResponse,
    summary="Get full message history for one of your own conversations",
)
async def get_own_conversation(
    conv_id: uuid.UUID,
    current_user: AnyAuthenticatedDep,
) -> ConversationHistoryResponse:
    pool = await get_pool()
    return await session_service.get_own_conversation(pool, conv_id, current_user.id)


# ═════════════════════════════════════════════
#  Target-user session — ADMIN / SUPERADMIN only
# ═════════════════════════════════════════════

@router.post(
    "/chat/{target_user_id}",
    response_model=ChatResponse,
    summary="Chat within another user's session (Admin / Superadmin only)",
)
async def chat_as_target(
    target_user_id: str,
    payload: ChatRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> ChatResponse:
    _block_users(current_user)
    pool = await get_pool()
    return await session_service.chat_as_target(
        pool, request, payload, target_user_id, current_user.id, current_user.role
    )


@router.delete(
    "/{target_user_id}",
    response_model=MessageResponse,
    summary="Clear another user's in-memory session (Admin / Superadmin only)",
)
async def clear_target_session(
    target_user_id: str,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> MessageResponse:
    _block_users(current_user)
    pool = await get_pool()
    return await session_service.clear_target_session(
        pool, request, target_user_id, current_user.id, current_user.role
    )


@router.get(
    "/{target_user_id}/conversations",
    response_model=UserConversationsResponse,
    summary="List another user's persisted conversations (Admin / Superadmin only)",
)
async def list_target_conversations(
    target_user_id: uuid.UUID,
    current_user: AnyAuthenticatedDep,
) -> UserConversationsResponse:
    _block_users(current_user)
    pool = await get_pool()
    return await session_service.list_target_conversations(
        pool, target_user_id, current_user.id, current_user.role
    )


@router.get(
    "/{target_user_id}/conversations/{conv_id}",
    response_model=ConversationHistoryResponse,
    summary="Get full message history for another user's conversation (Admin / Superadmin only)",
)
async def get_target_conversation(
    target_user_id: uuid.UUID,
    conv_id: uuid.UUID,
    current_user: AnyAuthenticatedDep,
) -> ConversationHistoryResponse:
    _block_users(current_user)
    pool = await get_pool()
    return await session_service.get_target_conversation(
        pool, target_user_id, conv_id, current_user.id, current_user.role
    )