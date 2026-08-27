"""
services/session_service.py — Business logic for chat sessions and conversation history.

In-memory sessions (app.state.sessions) are keyed by user_id string for the
legacy `chat_own` flow, and by conversation_id string for the new
`new_chat` / `continue_chat` flows.  This keeps the two flows isolated so
switching between them never pollutes each other's context.

    app.state.sessions[user_id]          → legacy rolling session (chat_own)
    app.state.conv_sessions[conv_id]     → per-conversation history

Conversation ownership rules enforced here:
  - SUPERADMIN  → can target any user_id
  - ADMIN       → can only target users where created_by == current_user.id
  - USER        → blocked at route level (403); never reaches this layer
"""

from __future__ import annotations

import uuid

import asyncpg
from fastapi import HTTPException, Request, status

from uvfastapi.app.models import (
    ChatRequest,
    ChatResponse,
    ContinueChatRequest,
    ContinueChatResponse,
    ConversationHistoryResponse,
    ConversationSummary,
    MessageResponse,
    NewChatRequest,
    NewChatResponse,
    RenameConversationRequest,
    RenameConversationResponse,
    UserConversationsResponse,
)
from uvfastapi.database.auth_db import insert_audit_log
from uvfastapi.database.session_db import (
    create_conversation,
    get_conversation_by_id,
    delete_conversation_by_id_and_user,
    get_conversation_by_id_and_user,
    get_messages_for_conversation,
    insert_message,
    list_conversations,
    rename_conversation,
    rename_conversation_admin,
)
from uvfastapi.database.user_db import get_user_by_id, get_user_by_id_and_creator
from uvfastapi.rag_engine.orchestrator import orchestrate_retrieval_and_generation

# ─────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────

def _conv_sessions(request: Request) -> dict:
    """
    Lazily initialise app.state.conv_sessions if it doesn't exist yet.
    Keeps per-conversation in-memory history keyed by conversation_id string.
    """
    if not hasattr(request.app.state, "conv_sessions"):
        request.app.state.conv_sessions = {}
    return request.app.state.conv_sessions


def _history_from_db(message_rows: list[asyncpg.Record]) -> list[dict]:
    """
    Convert DB message rows into the list-of-dicts format the LLM orchestrator
    expects: [{"role": "user"|"assistant", "content": "..."}]
    """
    return [
        {
            "role": (
                row["role"] if isinstance(row["role"], str) else row["role"].value
            ).lower(),
            "content": row["content"],
        }
        for row in message_rows
    ]


async def _verify_target_access(
    pool: asyncpg.Pool,
    target_user_id: uuid.UUID,
    caller_id: str,
    caller_role: str,
) -> None:
    """
    Verify the caller has permission to act on target_user_id.

    SUPERADMIN — any target is allowed; raises 404 only if user doesn't exist.
    ADMIN      — target must exist AND be created by this admin.
    """
    if caller_role == "SUPERADMIN":
        target = await get_user_by_id(pool, target_user_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found.",
            )
    else:
        # ADMIN path
        target = await get_user_by_id_and_creator(
            pool, target_user_id, uuid.UUID(caller_id)
        )
        if not target:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this user's session.",
            )


async def _get_or_create_conversation(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """
    Return the most recent active conversation ID for the user,
    or create a new one if none exists.

    Used only by the legacy chat_own / chat_as_target flows.
    """
    rows = await list_conversations(pool, user_id)
    if rows:
        return rows[0]["conversation_id"]
    conv = await create_conversation(pool, user_id=user_id)
    return conv["id"]


# ─────────────────────────────────────────────
#  Own session — available to every role
# ─────────────────────────────────────────────

async def chat_own(
    pool: asyncpg.Pool,
    request: Request,
    payload: ChatRequest,
    current_user_id: str,
) -> ChatResponse:
    """
    Send a message in the caller's own rolling session and return the LLM reply.

    Steps:
      1. Retrieve in-memory history
      2. Call LLM
      3. Update in-memory session
      4. Persist user + assistant messages to DB
      5. Audit
    """
    user_uuid = uuid.UUID(current_user_id)
    sessions = request.app.state.sessions

    # 1. In-memory history
    history = sessions.get(current_user_id, [])

    # 2. LLM call
    reply, updated_history = await orchestrate_retrieval_and_generation(
        request.app.state.embedding_function,
        payload.query,
        history,
    )

    # 3. Update in-memory state
    sessions[current_user_id] = updated_history

    # 4. Persist to DB
    conv_id = await _get_or_create_conversation(pool, user_uuid)
    await insert_message(pool, conversation_id=conv_id, role="USER",      content=payload.query)
    await insert_message(pool, conversation_id=conv_id, role="ASSISTANT", content=reply)

    # 5. Audit
    await insert_audit_log(
        pool,
        action="session.chat",
        user_id=user_uuid,
        resource_type="conversation",
        resource_id=conv_id,
    )

    return ChatResponse(reply=reply, user_id=current_user_id)


async def new_chat(
    pool: asyncpg.Pool,
    request: Request,
    payload: NewChatRequest,
    current_user_id: str,
) -> NewChatResponse:
    """
    Start a brand-new conversation, send the first message, and return the reply.

    Always creates a fresh Conversation row regardless of any existing ones.
    The returned conversation_id should be stored by the client and passed to
    continue_chat for all subsequent messages in this thread.

    Steps:
      1. Create a new Conversation row (with optional title)
      2. Seed the per-conversation in-memory cache as empty
      3. Call LLM with empty history
      4. Store updated history in per-conversation cache
      5. Persist user + assistant messages to DB
      6. Audit
    """
    user_uuid = uuid.UUID(current_user_id)

    # 1. Always create a fresh conversation
    conv = await create_conversation(pool, user_id=user_uuid, title=payload.title)
    conv_id: uuid.UUID = conv["id"]
    conv_key = str(conv_id)

    # 2. Start with an empty history for this new conversation
    conv_sessions = _conv_sessions(request)
    conv_sessions[conv_key] = []

    # 3. LLM call
    reply, updated_history = await orchestrate_retrieval_and_generation(
        request.app.state.embedding_function,
        payload.query,
        [],
    )

    # 4. Cache updated history under conversation key
    conv_sessions[conv_key] = updated_history

    # 5. Persist
    await insert_message(pool, conversation_id=conv_id, role="USER",      content=payload.query)
    await insert_message(pool, conversation_id=conv_id, role="ASSISTANT", content=reply)

    # 6. Audit
    await insert_audit_log(
        pool,
        action="session.new_chat",
        user_id=user_uuid,
        resource_type="conversation",
        resource_id=conv_id,
    )

    return NewChatResponse(conversation_id=conv_id, reply=reply, user_id=current_user_id)


async def continue_chat(
    pool: asyncpg.Pool,
    request: Request,
    payload: ContinueChatRequest,
    current_user_id: str,
) -> ContinueChatResponse:
    """
    Continue an existing conversation by its ID.

    History is loaded from the per-conversation in-memory cache when available
    (i.e. the server hasn't restarted), or rebuilt from the DB on a cache miss.
    This means conversation context survives across multiple requests as long as
    the process is running, and gracefully recovers from restarts.

    Steps:
      1. Verify the conversation exists and belongs to this user
      2. Load history from cache or DB
      3. Call LLM with the full prior history
      4. Update in-memory cache
      5. Persist user + assistant messages to DB
      6. Audit
    """
    user_uuid = uuid.UUID(current_user_id)
    conv_id = payload.conversation_id
    conv_key = str(conv_id)

    # 1. Ownership check — returns 404 for missing / other user's conversations
    conv = await get_conversation_by_id_and_user(pool, conv_id, user_uuid)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    # 2. History: prefer in-memory cache, fall back to DB
    conv_sessions = _conv_sessions(request)
    if conv_key in conv_sessions:
        history = conv_sessions[conv_key]
    else:
        # Cache miss (e.g. server restart) — rebuild from DB
        db_messages = await get_messages_for_conversation(pool, conv_id)
        history = _history_from_db(db_messages)

    # 3. LLM call with full prior history
    reply, updated_history = await orchestrate_retrieval_and_generation(
        request.app.state.embedding_function,
        payload.query,
        history,
    )

    # 4. Update cache
    conv_sessions[conv_key] = updated_history

    # 5. Persist
    await insert_message(pool, conversation_id=conv_id, role="USER",      content=payload.query)
    await insert_message(pool, conversation_id=conv_id, role="ASSISTANT", content=reply)

    # 6. Audit
    await insert_audit_log(
        pool,
        action="session.continue_chat",
        user_id=user_uuid,
        resource_type="conversation",
        resource_id=conv_id,
    )

    return ContinueChatResponse(conversation_id=conv_id, reply=reply, user_id=current_user_id)


async def rename_own_conversation(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
    payload: RenameConversationRequest,
    current_user_id: str,
) -> RenameConversationResponse:
    """
    Rename a conversation that belongs to the calling user.
    Returns 404 if the conversation doesn't exist or belongs to someone else.
    """
    user_uuid = uuid.UUID(current_user_id)

    updated = await rename_conversation(pool, conv_id, user_uuid, payload.title)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    await insert_audit_log(
        pool,
        action="session.conversation_renamed",
        user_id=user_uuid,
        resource_type="conversation",
        resource_id=conv_id,
        details={"new_title": payload.title},
    )

    return RenameConversationResponse(
        conversation_id=updated["id"],
        title=updated["title"],
        message="Conversation renamed successfully.",
    )

async def clear_entire_conversation(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
    current_user_id: str,
):
    user_uuid = uuid.UUID(current_user_id)
    
    conv = await delete_conversation_by_id_and_user(pool, conv_id, user_uuid)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) 
    return {"message":"Successfully deleted conversation", "data":[]}

async def clear_own_session(
    pool: asyncpg.Pool,
    request: Request,
    current_user_id: str,
) -> MessageResponse:
    """Pop the caller's in-memory rolling session. DB history is preserved."""
    request.app.state.sessions.pop(current_user_id, None)

    await insert_audit_log(
        pool,
        action="session.cleared",
        user_id=uuid.UUID(current_user_id),
        resource_type="user",
        resource_id=uuid.UUID(current_user_id),
    )

    return MessageResponse(message="Your session has been cleared.")


async def list_own_conversations(
    pool: asyncpg.Pool,
    current_user_id: str,
) -> UserConversationsResponse:
    rows = await list_conversations(pool, uuid.UUID(current_user_id))
    convs = [
        ConversationSummary(
            conversation_id=r["conversation_id"],
            title=r["title"],
            created_at=r["created_at"],
            message_count=r["message_count"],
        )
        for r in rows
    ]
    return UserConversationsResponse(user_id=current_user_id, conversations=convs)


async def get_own_conversation(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
    current_user_id: str,
) -> ConversationHistoryResponse:
    user_uuid = uuid.UUID(current_user_id)

    conv = await get_conversation_by_id_and_user(pool, conv_id, user_uuid)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    messages = await get_messages_for_conversation(pool, conv_id)
    return _build_history_response(current_user_id, messages)


# ─────────────────────────────────────────────
#  Target-user session — ADMIN / SUPERADMIN only
# ─────────────────────────────────────────────

async def chat_as_target(
    pool: asyncpg.Pool,
    request: Request,
    payload: ChatRequest,
    target_user_id: str,
    caller_id: str,
    caller_role: str,
) -> ChatResponse:
    """
    Chat within the target user's rolling session on their behalf.
    Caller must be ADMIN (owning the target) or SUPERADMIN.
    """
    target_uuid = uuid.UUID(target_user_id)

    # 1. Ownership check
    await _verify_target_access(pool, target_uuid, caller_id, caller_role)

    sessions = request.app.state.sessions

    # 2. In-memory history for the target
    history = sessions.get(target_user_id, [])

    # 3. LLM call
    reply, updated_history = await orchestrate_retrieval_and_generation(
        request.app.state.embedding_function,
        payload.query,
        history,
    )

    # 4. Update in-memory state
    sessions[target_user_id] = updated_history

    # 5. Persist
    conv_id = await _get_or_create_conversation(pool, target_uuid)
    await insert_message(pool, conversation_id=conv_id, role="USER",      content=payload.query)
    await insert_message(pool, conversation_id=conv_id, role="ASSISTANT", content=reply)

    # 6. Audit (record both the actor and the target)
    await insert_audit_log(
        pool,
        action="session.chat_as_target",
        user_id=uuid.UUID(caller_id),
        resource_type="conversation",
        resource_id=conv_id,
        details={"target_user_id": target_user_id},
    )

    return ChatResponse(reply=reply, user_id=target_user_id)


async def rename_target_conversation(
    pool: asyncpg.Pool,
    target_user_id: uuid.UUID,
    conv_id: uuid.UUID,
    payload: RenameConversationRequest,
    caller_id: str,
    caller_role: str,
) -> RenameConversationResponse:
    """
    Rename a conversation belonging to a target user.
    Caller must be ADMIN (owning the target) or SUPERADMIN.

    Verifies:
      1. Caller has access to the target user.
      2. The conversation belongs to the target user (no cross-user rename).
    """
    # 1. Access check on the user
    await _verify_target_access(pool, target_user_id, caller_id, caller_role)

    # 2. Confirm the conversation actually belongs to the target
    conv = await get_conversation_by_id_and_user(pool, conv_id, target_user_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    # 3. Perform the rename (admin variant — no user_id filter in UPDATE)
    updated = await rename_conversation_admin(pool, conv_id, payload.title)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    await insert_audit_log(
        pool,
        action="session.conversation_renamed",
        user_id=uuid.UUID(caller_id),
        resource_type="conversation",
        resource_id=conv_id,
        details={
            "target_user_id": str(target_user_id),
            "new_title": payload.title,
        },
    )

    return RenameConversationResponse(
        conversation_id=updated["id"],
        title=updated["title"],
        message=f"Conversation renamed successfully for user '{target_user_id}'.",
    )


async def clear_target_session(
    pool: asyncpg.Pool,
    request: Request,
    target_user_id: str,
    caller_id: str,
    caller_role: str,
) -> MessageResponse:
    target_uuid = uuid.UUID(target_user_id)
    await _verify_target_access(pool, target_uuid, caller_id, caller_role)

    request.app.state.sessions.pop(target_user_id, None)

    await insert_audit_log(
        pool,
        action="session.cleared",
        user_id=uuid.UUID(caller_id),
        resource_type="user",
        resource_id=target_uuid,
        details={"target_user_id": target_user_id, "cleared_by": caller_id},
    )

    return MessageResponse(message=f"Session cleared for user '{target_user_id}'.")


async def list_target_conversations(
    pool: asyncpg.Pool,
    target_user_id: uuid.UUID,
    caller_id: str,
    caller_role: str,
) -> UserConversationsResponse:
    await _verify_target_access(pool, target_user_id, caller_id, caller_role)

    rows = await list_conversations(pool, target_user_id)
    convs = [
        ConversationSummary(
            conversation_id=r["conversation_id"],
            title=r["title"],
            created_at=r["created_at"],
            message_count=r["message_count"],
        )
        for r in rows
    ]
    return UserConversationsResponse(user_id=str(target_user_id), conversations=convs)


async def get_target_conversation(
    pool: asyncpg.Pool,
    target_user_id: uuid.UUID,
    conv_id: uuid.UUID,
    caller_id: str,
    caller_role: str,
) -> ConversationHistoryResponse:
    await _verify_target_access(pool, target_user_id, caller_id, caller_role)

    # Verify the conversation actually belongs to the target
    conv = await get_conversation_by_id_and_user(pool, conv_id, target_user_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    messages = await get_messages_for_conversation(pool, conv_id)
    return _build_history_response(str(target_user_id), messages)


# ─────────────────────────────────────────────
#  Shared response builder
# ─────────────────────────────────────────────

def _build_history_response(
    user_id: str,
    message_rows: list[asyncpg.Record],
) -> ConversationHistoryResponse:
    from uvfastapi.app.models import ChatMessage

    messages = [
        ChatMessage(
            role=row["role"] if isinstance(row["role"], str) else row["role"].value,
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in message_rows
    ]
    return ConversationHistoryResponse(
        user_id=user_id,
        conversation_history=messages,
        total_messages=len(messages),
    )