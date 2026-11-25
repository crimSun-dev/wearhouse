"""Weather cache + per-user BMKG location (build-wearhouse-wardrobe-planning-services, 0007)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

weather_cache = Table(
    "weather_cache", metadata,
    Column("adm4", Text, primary_key=True),
    Column("slots", JSONB, nullable=False),
    Column("fetched_at", TS, nullable=False),
    Column("fresh_until", TS, nullable=False),
)

user_weather_location = Table(
    "user_weather_location", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("adm4", Text, nullable=False),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint(r"adm4 ~ '^\d{2}\.\d{2}\.\d{2}\.\d{4}$'", name="adm4"),
)
