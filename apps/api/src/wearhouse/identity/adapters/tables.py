from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Table, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

app_user = Table(
    "app_user", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("display_name", Text, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("tokens_not_before", TS, nullable=True),  # sign out everywhere: tokens with iat <= this are rejected
    Column("deleted_at", TS, nullable=True),  # tombstone: no personal data remains once set
)

user_subject = Table(
    "user_subject", metadata,
    Column("issuer", Text, primary_key=True),
    Column("subject", Text, primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Index("ix_user_subject_user_id", "user_id"),
)

role_grant = Table(
    "role_grant", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("role", Text, primary_key=True),
    Column("granted_by", Text, nullable=False),
    Column("granted_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("role IN ('catalogue_editor', 'inventory_manager', 'moderator', 'admin')", name="role"),
)
