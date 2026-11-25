from __future__ import annotations

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, Date, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Table, Text,
                        UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

catalogue_source = Table(
    "catalogue_source", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("namespace", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("namespace ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="namespace"),
)

source_snapshot = Table(
    "source_snapshot", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source_id", UUID(as_uuid=True), ForeignKey("catalogue_source.id"), nullable=False),
    Column("sha256", Text, nullable=False),
    Column("file_name", Text, nullable=False),
    Column("acquired_on", Date, nullable=False),
    Column("permission", JSONB, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    UniqueConstraint("source_id", "sha256"),
    CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
)

product = Table(
    "product", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source_id", UUID(as_uuid=True), ForeignKey("catalogue_source.id"), nullable=False),
    Column("external_id", Text, nullable=False),
    Column("gtin", Text, nullable=True),
    Column("gtin_scheme", Text, nullable=True),
    Column("gtin_evidence", Text, nullable=True),
    Column("catalogue_status", Text, nullable=False, server_default=text("'active'")),
    Column("current_revision_id", UUID(as_uuid=True), nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    # publish-wearhouse-catalogue (0005): publication pointer + denormalised browse fields written on publish
    Column("publication_state", Text, nullable=False, server_default=text("'draft'")),
    Column("published_revision_id", UUID(as_uuid=True), nullable=True),
    Column("published_at", TS, nullable=True),
    Column("retired_at", TS, nullable=True),
    Column("browse_name", Text, nullable=True),
    Column("browse_category", Text, nullable=True),
    Column("browse_colour", Text, nullable=True),
    Column("browse_slot", Text, nullable=True),
    Column("browse_text", Text, nullable=True),
    # add-wearhouse-sizes (0012): 'system:code' of product_size, denormalised so a size filter can follow the
    # newest-first index (common sizes) or the GIN index (rare sizes); product_size stays the source of truth
    Column("browse_sizes", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    UniqueConstraint("source_id", "external_id"),
    ForeignKeyConstraint(["published_revision_id"], ["product_revision.id"], use_alter=True,
                         name="fk_product_published_revision_id_product_revision"),
    CheckConstraint("publication_state IN ('draft', 'published', 'retired')", name="publication_state"),
    CheckConstraint("publication_state <> 'published' OR published_revision_id IS NOT NULL",
                    name="published_has_revision"),
    Index("ix_product_browse", "publication_state", "published_at", "id"),
    # add-wearhouse-object-management (0009): real-scale browse (105k products)
    Index("ix_product_browse_text_trgm", "browse_text", postgresql_using="gin",
          postgresql_ops={"browse_text": "gin_trgm_ops"}, postgresql_where=text("publication_state = 'published'")),
    Index("ix_product_pub_category", "browse_category", postgresql_where=text("publication_state = 'published'")),
    Index("ix_product_pub_colour", "browse_colour", postgresql_where=text("publication_state = 'published'")),
    Index("ix_product_pub_slot", "browse_slot", postgresql_where=text("publication_state = 'published'")),
    Index("ix_product_browse_sizes", "browse_sizes", postgresql_using="gin",
          postgresql_where=text("publication_state = 'published'")),
    ForeignKeyConstraint(["current_revision_id"], ["product_revision.id"], use_alter=True,
                         name="fk_product_current_revision_id_product_revision"),
    CheckConstraint("catalogue_status IN ('active', 'retired')", name="catalogue_status"),
    CheckConstraint("(gtin IS NULL AND gtin_scheme IS NULL AND gtin_evidence IS NULL) OR "
                    "(gtin IS NOT NULL AND gtin_scheme IS NOT NULL AND gtin_evidence IS NOT NULL)",
                    name="gtin_evidence"),
)

product_revision = Table(
    "product_revision", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=False),
    Column("revision_no", Integer, nullable=False),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("source_snapshot.id"), nullable=False),
    Column("content_digest", Text, nullable=False),
    Column("original_fields", JSONB, nullable=False),
    Column("facts", JSONB, nullable=False),
    Column("annotations", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_by", UUID(as_uuid=True), nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    UniqueConstraint("product_id", "revision_no"),
    CheckConstraint("revision_no >= 1", name="revision_no"),
)

product_variant = Table(
    "product_variant", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("revision_id", UUID(as_uuid=True), ForeignKey("product_revision.id"), nullable=False),
    Column("variant_key", Text, nullable=False),
    Column("facts", JSONB, nullable=False),
    UniqueConstraint("revision_id", "variant_key"),
)

media_reference = Table(
    "media_reference", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("revision_id", UUID(as_uuid=True), ForeignKey("product_revision.id"), nullable=False),
    Column("uri", Text, nullable=False),
    Column("media_version", Text, nullable=False),
    Column("rights", JSONB, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    UniqueConstraint("revision_id", "uri", "media_version"),
)


catalogue_import_job = Table(
    "catalogue_import_job", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source_id", UUID(as_uuid=True), ForeignKey("catalogue_source.id"), nullable=False),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("source_snapshot.id"), nullable=False),
    Column("mapping_version", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("totals", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_by", UUID(as_uuid=True), nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("completed_at", TS, nullable=True),
    CheckConstraint("status IN ('running', 'completed')", name="status"),
)

catalogue_import_row = Table(
    "catalogue_import_row", metadata,
    Column("job_id", UUID(as_uuid=True), ForeignKey("catalogue_import_job.id"), primary_key=True),
    Column("row_no", Integer, primary_key=True),
    Column("external_id", Text, nullable=True),
    Column("outcome", Text, nullable=False),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=True),
    Column("revision_no", Integer, nullable=True),
    Column("errors", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    CheckConstraint("outcome IN ('created', 'revised', 'unchanged', 'rejected')", name="outcome"),
)

catalogue_collection = Table(
    "catalogue_collection", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False, unique=True),
    Column("title", Text, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="slug"),
)

catalogue_collection_item = Table(
    "catalogue_collection_item", metadata,
    Column("collection_id", UUID(as_uuid=True), ForeignKey("catalogue_collection.id"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    Column("position", Integer, nullable=False),
)


product_media = Table(
    "product_media", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("content_type", Text, nullable=False),
    Column("data", LargeBinary, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("byte_size", BigInteger, nullable=False),
    Column("alt_text", Text, nullable=True),
    Column("position", Integer, nullable=False),
    Column("rights", JSONB, nullable=False),
    Column("generator", Text, nullable=True),
    Column("status", Text, nullable=False, server_default=text("'active'")),
    Column("created_by", UUID(as_uuid=True), nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("removed_at", TS, nullable=True),
    CheckConstraint("kind IN ('generated', 'uploaded')", name="kind"),
    CheckConstraint("content_type IN ('image/svg+xml', 'image/png', 'image/jpeg', 'image/webp')", name="content_type"),
    CheckConstraint("kind = 'generated' OR content_type <> 'image/svg+xml'", name="svg_only_generated"),
    CheckConstraint("byte_size BETWEEN 1 AND 5242880", name="byte_size"),
    CheckConstraint("status IN ('active', 'removed')", name="status"),
    CheckConstraint("alt_text IS NULL OR char_length(alt_text) <= 200", name="alt_text"),
    Index("ix_product_media_product_active", "product_id", "position", postgresql_where=text("status = 'active'")),
)


# ------------------------------------------------------------------ sizes (add-wearhouse-sizes, 0011)
size_system = Table(
    "size_system", metadata,
    Column("code", Text, primary_key=True),
    Column("label", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("slots", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("code ~ '^[a-z][a-z0-9_]{1,31}$'", name="code"),
)

size_value = Table(
    "size_value", metadata,
    Column("system_code", Text, ForeignKey("size_system.code"), primary_key=True),
    Column("code", Text, primary_key=True),
    Column("label", Text, nullable=False),
    Column("rank", Integer, nullable=False),
    Column("common", Boolean, nullable=False, server_default=text("true")),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("code ~ '^[A-Za-z0-9.]{1,8}$'", name="code"),
)

product_size = Table(
    "product_size", metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    Column("system_code", Text, primary_key=True),
    Column("size_code", Text, primary_key=True),
    Column("origin", Text, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    ForeignKeyConstraint(["system_code", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_product_size_size_value"),
    CheckConstraint("origin IN ('rule', 'staff')", name="origin"),
    Index("ix_product_size_lookup", "system_code", "size_code", "product_id"),
)

user_size_preference = Table(
    "user_size_preference", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("system_code", Text, primary_key=True),
    Column("size_code", Text, nullable=False),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    ForeignKeyConstraint(["system_code", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_user_size_preference_size_value"),
)
