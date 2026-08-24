"""
models.py — SQLAlchemy ORM models for chatbot with RBAC.

Roles:  superadmin  →  admin  →  user
Tables: users, conversations, messages, refresh_tokens, audit_logs
DB:     PostgreSQL (uses UUID, JSONB, timezone-aware timestamps)
"""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


#  Base

class Base(DeclarativeBase):
    pass


#  Python-level enums (mirrored as PG enums)

class UserRole(str, PyEnum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN      = "ADMIN"
    USER       = "USER"


class MessageRole(str, PyEnum):
    USER      = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM    = "SYSTEM"


#  Users

class User(Base):
    """
    Central identity table.

    - Soft-delete via deleted_at (never physically removed).
    - created_by tracks which admin/superadmin provisioned this account.
    - Passwords are NEVER stored; only bcrypt hashes go in hashed_password.
    - is_verified: email-verification gate before allowing login.
    """
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email           = Column(String(255), nullable=False)
    username        = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(
                          Enum(UserRole, name="userrole"),
                          nullable=False,
                          default=UserRole.USER,
                      )
    is_active       = Column(Boolean, nullable=False, default=True)
    is_verified     = Column(Boolean, nullable=False, default=False)

    # Who created this account (NULL for the bootstrapped superadmin)
    created_by      = Column(
                          UUID(as_uuid=True),
                          ForeignKey("users.id", ondelete="SET NULL"),
                          nullable=True,
                      )

    last_login_at   = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at      = Column(DateTime(timezone=True), nullable=True)   # soft-delete

    # ── relationships ──────────────────────────────────────────
    creator         = relationship("User", remote_side="User.id", foreign_keys=[created_by])
    conversations   = relationship(
                          "Conversation",
                          back_populates="user",
                          foreign_keys="Conversation.user_id",
                          passive_deletes=True,
                      )
    refresh_tokens  = relationship("RefreshToken", back_populates="user", passive_deletes=True)
    audit_logs      = relationship(
                          "AuditLog",
                          back_populates="actor",
                          foreign_keys="AuditLog.user_id",
                      )

    # ── indexes ────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),

        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_role", "role"),

        # Active users only
        Index(
            "ix_users_active_email",
            "email",
            postgresql_where=deleted_at.is_(None),
        ),

        Index("ix_users_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


#  Conversations

class Conversation(Base):
    """
    One chat session per row.

    - meta (JSONB): store model settings, system prompt overrides, etc.
      without changing the schema.
    - Soft-deleted; never hard-deleted so audit/billing history is intact.
    """
    __tablename__ = "conversations"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(
                      UUID(as_uuid=True),
                      ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=False,
                  )
    title       = Column(String(500), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    meta        = Column(JSONB, nullable=True, default=dict)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at  = Column(DateTime(timezone=True), nullable=True)

    user     = relationship("User", back_populates="conversations", foreign_keys=[user_id])
    messages = relationship(
                   "Message",
                   back_populates="conversation",
                   order_by="Message.created_at",
                   passive_deletes=True,
               )

    __table_args__ = (
        Index("ix_conversations_user_id",   "user_id"),
        Index("ix_conversations_created_at","created_at"),
        Index("ix_conversations_deleted_at","deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id}>"


#  Messages

class Message(Base):
    """
    Individual turn in a conversation.

    - role: user | assistant | system  (mirrors the LLM API contract)
    - token_count: store prompt+completion tokens for billing/analytics.
    - meta (JSONB): latency_ms, model_version, finish_reason, tool calls, etc.
    - Messages are NOT soft-deleted; delete cascades from conversation.
    """
    __tablename__ = "messages"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
                          UUID(as_uuid=True),
                          ForeignKey("conversations.id", ondelete="CASCADE"),
                          nullable=False,
                      )
    role            = Column(Enum(MessageRole, name="messagerole"), nullable=False)
    content         = Column(Text, nullable=False)
    token_count     = Column(Integer, nullable=True)
    meta            = Column(JSONB, nullable=True, default=dict)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created_at",      "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role} conv={self.conversation_id}>"


#  Refresh Tokens

class RefreshToken(Base):
    """
    JWT refresh-token registry.

    - Store only the SHA-256 hash of the token, never the raw value.
    - is_revoked: allow explicit logout / token rotation without waiting for expiry.
    - ip_address / user_agent: device fingerprinting for anomaly detection.
    - Expired + revoked rows can be purged by a nightly cron.
    """
    __tablename__ = "refresh_tokens"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(
                      UUID(as_uuid=True),
                      ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=False,
                  )
    token_hash  = Column(String(255), unique=True, nullable=False)   # SHA-256 hex
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    is_revoked  = Column(Boolean, nullable=False, default=False)
    ip_address  = Column(String(45),  nullable=True)   # supports IPv6
    user_agent  = Column(String(500), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
        Index("ix_refresh_tokens_user_id",   "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.is_revoked}>"


#  Audit Logs

class AuditLog(Base):
    """
    Immutable event log for compliance & debugging.

    - user_id is nullable: system-initiated events (seeder, cron) have no actor.
    - action follows dot-notation convention: "user.created", "admin.role_changed".
    - resource_type + resource_id point at the affected row in any table.
    - details (JSONB): before/after snapshots, extra context — keep PII minimal.
    - This table should NEVER be updated or deleted. Use PG row-level security
      or a separate append-only role in production if needed.

    Production tip: partition this table by month (PARTITION BY RANGE created_at)
    once you expect millions of rows.
    """
    __tablename__ = "audit_logs"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(
                        UUID(as_uuid=True),
                        ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True,
                    )
    action        = Column(String(100), nullable=False)     # "user.created"
    resource_type = Column(String(100), nullable=True)      # "user" | "conversation" | …
    resource_id   = Column(UUID(as_uuid=True), nullable=True)
    ip_address    = Column(String(45),  nullable=True)
    user_agent    = Column(String(500), nullable=True)
    details       = Column(JSONB, nullable=True)            # before/after or extra ctx
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor = relationship("User", back_populates="audit_logs", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_audit_logs_user_id",   "user_id"),
        Index("ix_audit_logs_action",    "action"),
        Index("ix_audit_logs_created_at","created_at"),
        Index("ix_audit_logs_resource",  "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} actor={self.user_id}>"