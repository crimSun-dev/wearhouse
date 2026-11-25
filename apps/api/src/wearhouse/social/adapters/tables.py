"""add-wearhouse-social-profile-services (0008): look shares, plan sharing setting, notification read marker,
profile showcase. Visibility is never stored: it is computed at read time from the accounts policy."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

look_share = Table(
    "look_share", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("owner_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("look_id", UUID(as_uuid=True), ForeignKey("look.id"), nullable=False),
    Column("revision_id", UUID(as_uuid=True), ForeignKey("look_revision.id"), nullable=False),
    Column("audience", Text, nullable=False),
    Column("caption", Text, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("revoked_at", TS, nullable=True),
    Column("moderation_state", Text, nullable=False, server_default=text("'visible'")),  # 0015
    Column("moderated_by", UUID(as_uuid=True), nullable=True),
    Column("moderated_at", TS, nullable=True),
    Column("moderation_reason", Text, nullable=True),
    CheckConstraint("moderation_state IN ('visible', 'hidden')", name="moderation_state"),
    CheckConstraint("audience IN ('friends', 'public')", name="audience"),
    CheckConstraint("caption IS NULL OR char_length(caption) <= 140", name="caption"),
    Index("ix_look_share_owner_created", "owner_id", "created_at", "id"),
)

plan_share_setting = Table(
    "plan_share_setting", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("audience", Text, nullable=False),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("audience IN ('none', 'friends')", name="audience"),
)

notification_state = Table(
    "notification_state", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("read_through", TS, nullable=False),
)

profile_showcase = Table(
    "profile_showcase", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("headline", Text, nullable=True),
    Column("accent", Text, nullable=False, server_default=text("'plum'")),
    Column("featured", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("headline IS NULL OR char_length(headline) <= 80", name="headline"),
    CheckConstraint("accent IN ('plum', 'ivory', 'blush', 'noir', 'sage', 'sky')", name="accent"),
    CheckConstraint("jsonb_array_length(featured) <= 3", name="featured_max"),
)


# ------------------------------------------------------------------ moderation + inspiration (complete-wearhouse-tdd, 0015)
share_report = Table(
    "share_report", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("share_id", UUID(as_uuid=True), ForeignKey("look_share.id"), nullable=False),
    Column("reporter_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("reason", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'open'")),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("resolved_at", TS, nullable=True),
    UniqueConstraint("share_id", "reporter_id", name="uq_share_report_once"),
    CheckConstraint("status IN ('open', 'actioned', 'dismissed')", name="status"),
    CheckConstraint("char_length(reason) BETWEEN 1 AND 300", name="reason"),
    Index("ix_share_report_status_created", "status", "created_at"),
)

inspiration = Table(
    "inspiration", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("source_share_id", UUID(as_uuid=True), nullable=True),  # no FK: the snapshot outlives the share
    Column("snapshot", JSONB, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Index("ix_inspiration_user_created", "user_id", "created_at"),
)
