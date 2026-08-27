"""
models.py — Pydantic request / response schemas.

Organised by domain:
  Auth        → register, login, token refresh
  User        → create (admin-initiated), profile views
  Admin       → registration + approval
  SuperAdmin  → admin management
  Chat        → query, history
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


#  Shared / base

class MessageResponse(BaseModel):
    """Generic envelope returned by every endpoint."""
    message: str
    data: Any | None = None


#  Auth

class AdminRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, digits, hyphens and underscores.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


#  Users  (admin-initiated creation)

class CreateUserRequest(BaseModel):
    """Admin creates a user and sets an initial password."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, digits, hyphens and underscores.")
        return v


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserProfileResponse]
    total: int


#  Admin

class AdminProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    is_active: bool       # False until superadmin approves
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminListResponse(BaseModel):
    admins: list[AdminProfileResponse]
    total: int


#  SuperAdmin — admin management

class ApproveAdminResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    message: str


class PendingAdminResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


#  Chat

class ChatMessage(BaseModel):
    role: str           # "user" | "assistant" | "system"
    content: str
    created_at: datetime | None = None


class LLMQueryRequest(BaseModel):
    query: str
    user_id: str        # kept for backward-compat with existing /api/v1/query-llm


class ChatRequest(BaseModel):
    query: str


class NewChatRequest(BaseModel):
    """
    Start a brand-new conversation.
    An optional title can be supplied upfront; if omitted the conversation
    will have no title until the caller renames it later.
    """
    query: str
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional human-readable title for the new conversation.",
    )


class ContinueChatRequest(BaseModel):
    """Resume an existing conversation by its ID."""
    conversation_id: uuid.UUID
    query: str


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class ChatResponse(BaseModel):
    reply: str
    user_id: str


class NewChatResponse(BaseModel):
    """Returned by the new-chat endpoint — includes the conversation_id so the
    caller can reference the conversation in subsequent continue-chat calls."""
    conversation_id: uuid.UUID
    reply: str
    user_id: str


class ContinueChatResponse(BaseModel):
    """Returned by the continue-chat endpoint."""
    conversation_id: uuid.UUID
    reply: str
    user_id: str


class RenameConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    title: str
    message: str


class ConversationHistoryResponse(BaseModel):
    user_id: str
    conversation_history: list[ChatMessage]
    total_messages: int


class ConversationSummary(BaseModel):
    """One conversation belonging to a user — used in list views."""
    conversation_id: uuid.UUID
    title: str | None
    created_at: datetime
    message_count: int


class UserConversationsResponse(BaseModel):
    user_id: str
    conversations: list[ConversationSummary]