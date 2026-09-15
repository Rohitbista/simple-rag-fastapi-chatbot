"""
routes/session.py — All chat & session endpoints, unified across roles.

Every route uses `AnyAuthenticatedDep` for auth, then branches on
`current_user.role` where access rules differ.

Role access matrix:
┌──────────────────────────────────────────────────────────┬────────────┬───────┬──────┐
│ Endpoint                                                 │ SUPERADMIN │ ADMIN │ USER │
├──────────────────────────────────────────────────────────┼────────────┼───────┼──────┤
│ POST   /api/v1/session/chat                              │     ✓      │   ✓   │  ✓   │
│ POST   /api/v1/session/new-chat                          │     ✓      │   ✓   │  ✓   │
│ POST   /api/v1/session/continue-chat                     │     ✓      │   ✓   │  ✓   │
│ PATCH  /api/v1/session/conversations/{conv_id}/rename    │     ✓      │   ✓   │  ✓   │
│ DELETE /api/v1/session                                   │     ✓      │   ✓   │  ✓   │
│ GET    /api/v1/session/conversations                     │     ✓      │   ✓   │  ✓   │
│ GET    /api/v1/session/conversations/{conv_id}           │     ✓      │   ✓   │  ✓   │
├──────────────────────────────────────────────────────────┼────────────┼───────┼──────┤
│ POST   /api/v1/session/chat/{target_user_id}             │     ✓      │   ✓   │  ✗   │
│ DELETE /api/v1/session/{target_user_id}                  │     ✓      │   ✓   │  ✗   │
│ GET    /api/v1/session/{target_user_id}/conversations    │     ✓      │   ✓   │  ✗   │
│ GET    /api/v1/session/{target_user_id}/conv/{conv_id}   │     ✓      │   ✓   │  ✗   │
│ PATCH  /api/v1/session/{target_user_id}/conv/{conv_id}/rename │  ✓   │   ✓   │  ✗   │
└──────────────────────────────────────────────────────────┴────────────┴───────┴──────┘

Routing note — FastAPI matches routes top-to-bottom.  Static path segments
(e.g. "conversations", "new-chat") are declared BEFORE parameterised ones
(e.g. /{target_user_id}) so they are never swallowed by the wildcard.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from uvfastapi.app.middleware.auth import AnyAuthenticatedDep
from uvfastapi.app.models import (
    ChatRequest,
    ChatResponse,
    ContinueChatRequest,
    ContinueChatResponse,
    ConversationHistoryResponse,
    MessageResponse,
    NewChatRequest,
    NewChatResponse,
    RenameConversationRequest,
    RenameConversationResponse,
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


# ══════════════════════════════════════════════════════════
#  Own session — available to every role
#  NOTE: all static-segment routes come before /{target_user_id}
# ══════════════════════════════════════════════════════════

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message in your own rolling session and receive an LLM reply",
)
async def chat_own(
    payload: ChatRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> ChatResponse:
    pool = await get_pool()
    return await session_service.chat_own(pool, request, payload, current_user.id)


@router.post(
    "/new-chat",
    response_model=NewChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a brand-new conversation and send the first message",
)
async def new_chat(
    payload: NewChatRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> NewChatResponse:
    """
    Always creates a fresh Conversation row.
    The `conversation_id` in the response must be passed to
    `POST /continue-chat` for all follow-up messages in this thread.

    Body fields:
    - **query** – the first message to send.
    - **title** *(optional)* – a human-readable label for the conversation.
      If omitted you can set one later via the rename endpoint.
    """
    pool = await get_pool()
    return await session_service.new_chat(pool, request, payload, current_user.id)


@router.post(
    "/continue-chat",
    response_model=ContinueChatResponse,
    summary="Send a message inside an existing conversation",
)
async def continue_chat(
    payload: ContinueChatRequest,
    request: Request,
    current_user: AnyAuthenticatedDep,
) -> ContinueChatResponse:
    """
    Resume a conversation the caller previously started.

    Body fields:
    - **conversation_id** – UUID returned by `POST /new-chat`.
    - **query** – the next message to send.

    History is loaded from the server-side in-memory cache when available,
    or rebuilt transparently from the database on a cache miss (e.g. after
    a server restart) — the caller does not need to manage history.
    """
    pool = await get_pool()
    return await session_service.continue_chat(pool, request, payload, current_user.id)


@router.patch(
    "/conversations/{conv_id}/rename",
    response_model=RenameConversationResponse,
    summary="Rename one of your own conversations",
)
async def rename_own_conversation(
    conv_id: uuid.UUID,
    payload: RenameConversationRequest,
    current_user: AnyAuthenticatedDep,
) -> RenameConversationResponse:
    """
    Set or update the human-readable title of a conversation you own.

    Body fields:
    - **title** – the new name (1–500 characters).
    """
    pool = await get_pool()
    return await session_service.rename_own_conversation(
        pool, conv_id, payload, current_user.id
    )

@router.delete(
    "/conversations/{conv_id}",
    response_model=MessageResponse,
    summary="Delete an entire conversation history",
)
async def clear_own_session(
    conv_id: uuid.UUID,
    current_user: AnyAuthenticatedDep,
) -> MessageResponse:
    pool = await get_pool()
    return await session_service.clear_entire_conversation(pool, conv_id, current_user.id)

@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear your own in-memory rolling session (start a fresh conversation)",
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


# ══════════════════════════════════════════════════════════
#  Target-user session — ADMIN / SUPERADMIN only
#  These must come AFTER all static-segment routes above.
# ══════════════════════════════════════════════════════════

@router.post(
    "/chat/{target_user_id}",
    response_model=ChatResponse,
    summary="Chat within another user's rolling session (Admin / Superadmin only)",
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


@router.patch(
    "/{target_user_id}/conversations/{conv_id}/rename",
    response_model=RenameConversationResponse,
    summary="Rename another user's conversation (Admin / Superadmin only)",
)
async def rename_target_conversation(
    target_user_id: uuid.UUID,
    conv_id: uuid.UUID,
    payload: RenameConversationRequest,
    current_user: AnyAuthenticatedDep,
) -> RenameConversationResponse:
    """
    Set or update the title of a conversation belonging to a target user.
    The conversation must belong to that user — admins cannot rename across users.

    Body fields:
    - **title** – the new name (1–500 characters).
    """
    _block_users(current_user)
    pool = await get_pool()
    return await session_service.rename_target_conversation(
        pool, target_user_id, conv_id, payload, current_user.id, current_user.role
    )