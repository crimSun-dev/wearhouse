from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, LargeBinary, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

garment_unit = Table(
    "garment_unit", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=False),
    Column("acquisition_revision_id", UUID(as_uuid=True), ForeignKey("product_revision.id"), nullable=False),
    Column("public_serial", Text, nullable=False, unique=True),
    Column("status", Text, nullable=False),
    Column("issued_by", UUID(as_uuid=True), nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("claimed_at", TS, nullable=True),
    Column("size_system", Text, nullable=True),
    Column("size_code", Text, nullable=True),
    Column("size_label", Text, nullable=True),
    ForeignKeyConstraint(["size_system", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_garment_unit_size_value"),
    CheckConstraint("status IN ('issued', 'claimed', 'retired')", name="status"),
    CheckConstraint("public_serial ~ '^[a-z2-7]{26}$'", name="public_serial"),
)

activation_credential = Table(
    "activation_credential", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("unit_id", UUID(as_uuid=True), ForeignKey("garment_unit.id"), nullable=False),
    Column("key_digest", Text, nullable=False, unique=True),
    Column("status", Text, nullable=False),
    Column("audience_user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=True),
    Column("issued_by", UUID(as_uuid=True), nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("redeemed_at", TS, nullable=True),
    Column("revoked_at", TS, nullable=True),
    CheckConstraint("status IN ('active', 'redeemed', 'revoked')", name="status"),
    CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name="key_digest"),
    Index("uq_activation_credential_one_active_per_unit", "unit_id", unique=True,
          postgresql_where=text("status = 'active'")),
)

issuance_delivery = Table(
    "issuance_delivery", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("unit_id", UUID(as_uuid=True), ForeignKey("garment_unit.id"), nullable=False),
    Column("credential_id", UUID(as_uuid=True), ForeignKey("activation_credential.id"), nullable=False,
           unique=True),
    Column("actor_id", UUID(as_uuid=True), nullable=False),
    Column("key_id", Text, nullable=True),
    Column("nonce", LargeBinary, nullable=True),
    Column("ciphertext", LargeBinary, nullable=True),
    Column("expires_at", TS, nullable=False),
    Column("erased_at", TS, nullable=True),
    Column("erase_reason", Text, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("erased_at IS NULL OR (ciphertext IS NULL AND nonce IS NULL)", name="erased_has_no_secret"),
)

owned_item = Table(
    "owned_item", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("unit_id", UUID(as_uuid=True), ForeignKey("garment_unit.id"), nullable=False, unique=True),
    Column("acquisition_revision_id", UUID(as_uuid=True), ForeignKey("product_revision.id"), nullable=False),
    Column("presentation", JSONB, nullable=False),
    Column("claimed_at", TS, nullable=False),
    Column("created_at", TS, nullable=False),
    Column("revoked_at", TS, nullable=True),        # sandbox entitlement revoked (complete-wearhouse-tdd, 0015)
    Column("revoked_reason", Text, nullable=True),
    CheckConstraint("(revoked_at IS NULL) = (revoked_reason IS NULL)", name="revoked_pair"),
    Index("ix_owned_item_user_page", "user_id", "created_at", "id"),
)

ownership_event = Table(
    "ownership_event", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("unit_id", UUID(as_uuid=True), ForeignKey("garment_unit.id"), nullable=False),
    Column("item_id", UUID(as_uuid=True), ForeignKey("owned_item.id"), nullable=True),
    Column("user_id", UUID(as_uuid=True), nullable=True),
    Column("event_type", Text, nullable=False),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", TS, nullable=False, server_default=NOW),
)
