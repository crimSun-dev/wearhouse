"""Recommendation artifacts (complete-wearhouse-research-intelligence, 0010): versioned, sha-verified research
outputs imported for serving, plus their item-to-item neighbour lists."""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer, Table, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)

recommendation_artifact = Table(
    "recommendation_artifact", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("kind", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("version", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("model_hash", Text, nullable=True),
    Column("manifest", JSONB, nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("false")),
    Column("imported_by", UUID(as_uuid=True), nullable=True),
    Column("imported_at", TS, nullable=False, server_default=text("now()")),
    CheckConstraint("kind IN ('similar_items')", name="kind"),
    CheckConstraint("mode IN ('trained', 'heuristic_baseline')", name="mode"),
    CheckConstraint("mode <> 'trained' OR model_hash IS NOT NULL", name="trained_has_hash"),
    Index("uq_recommendation_artifact_active_kind", "kind", unique=True, postgresql_where=text("active")),
)

item_neighbour = Table(
    "item_neighbour", metadata,
    Column("artifact_id", UUID(as_uuid=True), ForeignKey("recommendation_artifact.id"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    Column("rank", Integer, primary_key=True),
    Column("neighbour_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=False),
    Column("score", Float, nullable=False),
)


# ------------------------------------------------------------------ outfit runs + feedback (align-wearhouse-outfit-recommender)
recommendation_run = Table(
    "recommendation_run", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("context", JSONB, nullable=False),       # date, occasion, weather, style, weights, ruleset
    Column("suggestions", JSONB, nullable=False),   # [[item_id, ...], ...] in the order shown
    Column("displayed_at", TS, nullable=True),
    Column("created_at", TS, nullable=False, server_default=text("now()")),
    Index("ix_recommendation_run_user_created", "user_id", "created_at"),
)

recommendation_exposure = Table(  # one row per (run, item): repeated "displayed" events never inflate counts
    "recommendation_exposure", metadata,
    Column("run_id", UUID(as_uuid=True), ForeignKey("recommendation_run.id"), primary_key=True),
    Column("item_id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Index("ix_recommendation_exposure_user_item", "user_id", "item_id"),
)

recommendation_choice = Table(  # at most one choice per run
    "recommendation_choice", metadata,
    Column("run_id", UUID(as_uuid=True), ForeignKey("recommendation_run.id"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("suggestion_index", Integer, nullable=False),
    Column("item_ids", ARRAY(UUID(as_uuid=True)), nullable=False),
    Column("chosen_at", TS, nullable=False),
    CheckConstraint("suggestion_index >= 0", name="index_non_negative"),
    Index("ix_recommendation_choice_user", "user_id"),
)
