"""
database/session_db.py — Raw asyncpg queries for conversations and messages.

Design notes:
  - Conversations are soft-deleted (deleted_at).
  - Messages hard-cascade from their conversation (no soft-delete needed).
  - `message_count` is derived via a subquery/COUNT — no separate counter column.
"""

from __future__ import annotations

import json
import uuid

import asyncpg


#  Conversations

async def list_conversations(
    pool: asyncpg.Pool,
    user_id: uuid.UUID,
) -> list[asyncpg.Record]:
    """
    All non-deleted conversations for a user, newest first.
    Includes a `message_count` derived from the messages table.
    """
    return await pool.fetch(
        """
        SELECT c.id              AS conversation_id,
               c.title,
               c.created_at,
               COUNT(m.id)::int AS message_count
          FROM conversations c
          LEFT JOIN messages m ON m.conversation_id = c.id
         WHERE c.user_id    = $1
           AND c.deleted_at IS NULL
         GROUP BY c.id
         ORDER BY c.created_at DESC
        """,
        user_id,
    )


async def get_conversation_by_id_and_user(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
    user_id: uuid.UUID,
) -> asyncpg.Record | None:
    """
    Fetch a conversation only when it belongs to the given user.
    Returns None for a different user's conversation (no info leak).
    """
    return await pool.fetchrow(
        """
        SELECT id, user_id, title, created_at
          FROM conversations
         WHERE id         = $1
           AND user_id    = $2
           AND deleted_at IS NULL
        """,
        conv_id,
        user_id,
    )


async def get_conversation_by_id(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
) -> asyncpg.Record | None:
    """Superadmin / admin override — fetch without user ownership check."""
    return await pool.fetchrow(
        """
        SELECT id, user_id, title, created_at
          FROM conversations
         WHERE id         = $1
           AND deleted_at IS NULL
        """,
        conv_id,
    )


async def create_conversation(
    pool: asyncpg.Pool,
    *,
    user_id: uuid.UUID,
    title: str | None = None,
    is_archived: bool = False,
) -> asyncpg.Record:
    """Insert a new conversation row and return it."""
    return await pool.fetchrow(
        """
        INSERT INTO conversations (id, user_id, title, is_archived, created_at, updated_at)
        VALUES ($1, $2, $3, $4, NOW(), NOW())
        RETURNING id, user_id, title, created_at
        """,
        uuid.uuid4(),
        user_id,
        title,
        is_archived,
    )


async def soft_delete_conversation(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
) -> None:
    await pool.execute(
        """
        UPDATE conversations
           SET deleted_at = NOW(),
               updated_at = NOW()
         WHERE id = $1
        """,
        conv_id,
    )


#  Messages

async def get_messages_for_conversation(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
) -> list[asyncpg.Record]:
    """All messages in a conversation, chronological order."""
    return await pool.fetch(
        """
        SELECT id, conversation_id, role, content, token_count, created_at
          FROM messages
         WHERE conversation_id = $1
         ORDER BY created_at ASC
        """,
        conv_id,
    )


async def insert_message(
    pool: asyncpg.Pool,
    *,
    conversation_id: uuid.UUID,
    role: str,          # "USER" | "ASSISTANT" | "SYSTEM"
    content: str,
    token_count: int | None = None,
    meta: dict | None = None,
) -> asyncpg.Record:
    """Append a message to a conversation and return the inserted row."""
    return await pool.fetchrow(
        """
        INSERT INTO messages
               (id, conversation_id, role, content, token_count, meta, created_at)
        VALUES ($1,       $2,         $3,     $4,       $5,       $6,   NOW())
        RETURNING id, conversation_id, role, content, created_at
        """,
        uuid.uuid4(),
        conversation_id,
        role,
        content,
        token_count,
        json.dumps(meta) if meta is not None else None,
    )


async def upsert_conversation_title(
    pool: asyncpg.Pool,
    conv_id: uuid.UUID,
    title: str,
) -> None:
    """Set / update the human-readable title of a conversation."""
    await pool.execute(
        """
        UPDATE conversations
           SET title      = $2,
               updated_at = NOW()
         WHERE id = $1
        """,
        conv_id,
        title,
    )