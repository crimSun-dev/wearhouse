"""Platform-owned tables: environment marker, idempotency, attempts, audit, outbox."""
from __future__ import annotations

from sqlalchemy import (Boolean, CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        SmallInteger, Table, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from .db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

wearhouse_environment = Table(
    "wearhouse_environment", metadata,
    Column("id", SmallInteger, primary_key=True),
    Column("app_family", Text, nullable=False),
    Column("environment", Text, nullable=False),
    Column("runtime_role", Text, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("id = 1", name="singleton"),
)

idempotency_record = Table(
    "idempotency_record", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("actor_id", UUID(as_uuid=True), nullable=False),
    Column("route", Text, nullable=False),
    Column("idem_key", Text, nullable=False),
    Column("request_fingerprint", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("lease_token", UUID(as_uuid=True), nullable=True),
    Column("lease_expires_at", TS, nullable=True),
    Column("attempt_reserved", Boolean, nullable=False, server_default=text("false")),
    Column("response_status", Integer, nullable=True),
    Column("response_body", JSONB, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("completed_at", TS, nullable=True),
    UniqueConstraint("actor_id", "route", "idem_key"),
    CheckConstraint("status IN ('processing', 'completed')", name="status"),
    CheckConstraint("status <> 'completed' OR response_status IS NOT NULL", name="completed_has_response"),
)

attempt_bucket = Table(
    "attempt_bucket", metadata,
    Column("scope", Text, primary_key=True),
    Column("scope_key", Text, primary_key=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("scope IN ('actor', 'ip', 'global', 'friend_request', 'export')", name="scope"),
)

attempt_event = Table(
    "attempt_event", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("scope", Text, nullable=False),
    Column("scope_key", Text, nullable=False),
    Column("reserved_at", TS, nullable=False),
    Column("idempotency_id", UUID(as_uuid=True), nullable=True),
    ForeignKeyConstraint(["scope", "scope_key"], ["attempt_bucket.scope", "attempt_bucket.scope_key"],
                         name="fk_attempt_event_bucket"),
    Index("ix_attempt_event_scope_window", "scope", "scope_key", "reserved_at"),
)

audit_event = Table(
    "audit_event", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("actor_id", UUID(as_uuid=True), nullable=True),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=False),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("request_id", Text, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
)

outbox_event = Table(
    "outbox_event", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("event_type", Text, nullable=False),
    Column("aggregate_type", Text, nullable=False),
    Column("aggregate_id", UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("available_at", TS, nullable=False, server_default=NOW),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("dispatched_at", TS, nullable=True),
    Column("last_error", Text, nullable=True),
    Index("ix_outbox_event_pending", "dispatched_at", "available_at"),
)

outbox_delivery = Table(
    "outbox_delivery", metadata,
    Column("consumer", Text, primary_key=True),
    Column("event_id", UUID(as_uuid=True), ForeignKey("outbox_event.id"), primary_key=True),
    Column("delivered_at", TS, nullable=False, server_default=NOW),
)
