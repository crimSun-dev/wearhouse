"""Accounts-owned tables: profiles, handle holds, privacy, friend requests, friendships, blocks."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")
VISIBILITY = "IN ('public', 'friends', 'private')"

account_profile = Table(
    "account_profile", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("handle", Text, nullable=True),
    Column("display_name", Text, nullable=False),
    Column("bio", Text, nullable=False, server_default=text("''")),
    Column("avatar_kind", Text, nullable=False, server_default=text("'preset'")),
    Column("avatar_preset", Text, nullable=True),
    Column("avatar_url", Text, nullable=True),
    Column("handle_changed_at", TS, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("handle IS NULL OR handle ~ '^[a-z][a-z0-9_]{2,19}$'", name="handle_format"),
    CheckConstraint("char_length(display_name) BETWEEN 1 AND 32", name="display_name_length"),
    CheckConstraint("char_length(bio) <= 160", name="bio_length"),
    CheckConstraint("(avatar_kind = 'preset' AND avatar_url IS NULL) OR "
                    "(avatar_kind = 'provider' AND avatar_url IS NOT NULL AND avatar_url LIKE 'https://%')",
                    name="avatar"),
    Index("uq_account_profile_handle", "handle", unique=True),
)

handle_hold = Table(
    "handle_hold", metadata,
    Column("handle", Text, primary_key=True),
    Column("held_for", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True),
    Column("available_at", TS, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
)

privacy_setting = Table(
    "privacy_setting", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("profile", Text, nullable=False, server_default=text("'public'")),
    Column("wardrobe", Text, nullable=False, server_default=text("'private'")),
    Column("friends_list", Text, nullable=False, server_default=text("'friends'")),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint(f"profile {VISIBILITY}", name="profile"),
    CheckConstraint(f"wardrobe {VISIBILITY}", name="wardrobe"),
    CheckConstraint(f"friends_list {VISIBILITY}", name="friends_list"),
)

friend_request = Table(
    "friend_request", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("from_user", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("to_user", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TS, nullable=False),
    Column("resolved_at", TS, nullable=True),
    CheckConstraint("status IN ('pending', 'accepted', 'declined', 'cancelled')", name="status"),
    CheckConstraint("from_user <> to_user", name="not_self"),
    Index("uq_friend_request_one_pending", "from_user", "to_user", unique=True,
          postgresql_where=text("status = 'pending'")),
    Index("ix_friend_request_incoming", "to_user", "status", "created_at", "id"),
    Index("ix_friend_request_outgoing", "from_user", "status", "created_at", "id"),
)

friendship = Table(
    "friendship", metadata,
    Column("user_low", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("user_high", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("created_at", TS, nullable=False),
    CheckConstraint("user_low < user_high", name="ordered_pair"),
    Index("ix_friendship_user_high", "user_high"),
)

user_block = Table(
    "user_block", metadata,
    Column("blocker", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("blocked", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("created_at", TS, nullable=False),
    CheckConstraint("blocker <> blocked", name="not_self"),
    Index("ix_user_block_blocked", "blocked"),
)


# add-wearhouse-settings-security (0013): only explicitly set keys are stored; defaults come from the registry
account_setting = Table(
    "account_setting", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("values", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("version", Integer, nullable=False, server_default=text("0")),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("jsonb_typeof(\"values\") = 'object'", name="values_object"),
)
