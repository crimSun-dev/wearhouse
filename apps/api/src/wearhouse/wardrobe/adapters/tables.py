"""build-wearhouse-wardrobe-planning-services (0007): declared items, item state, shelves, looks + immutable
revisions, plans and the wear log."""
from __future__ import annotations

from sqlalchemy import (CheckConstraint, Column, Date, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary,
                        Table, Text,
                        UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")
SLOT_CHECK = ("IN ('top', 'outer', 'bottom', 'dress', 'footwear', 'underwear', 'bag', 'headwear', 'eyewear', 'earrings', "
              "'necklace', 'tie', 'scarf', 'belt', 'wrist', 'ring', 'accessory')")  # underwear slot (0016)

wardrobe_declared_item = Table(
    "wardrobe_declared_item", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("slot", Text, nullable=False),
    Column("category", Text, nullable=True),
    Column("colour", Text, nullable=True),
    Column("photo", LargeBinary, nullable=True),
    Column("photo_type", Text, nullable=True),
    Column("photo_sha256", Text, nullable=True),
    Column("archived_at", TS, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("slot " + SLOT_CHECK, name="slot"),
    CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name"),
    CheckConstraint("photo IS NULL OR octet_length(photo) <= 2097152", name="photo_size"),
    CheckConstraint("photo_type IS NULL OR photo_type IN ('image/jpeg', 'image/png', 'image/webp')", name="photo_type"),
    Index("ix_wardrobe_declared_item_user", "user_id", "created_at"),
)

wardrobe_item_state = Table(
    "wardrobe_item_state", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("item_id", UUID(as_uuid=True), primary_key=True),
    Column("care_state", Text, nullable=False, server_default=text("'ready'")),
    Column("slot_override", Text, nullable=True),
    Column("size_system", Text, nullable=True),  # the owner's size correction (add-wearhouse-sizes D6)
    Column("size_code", Text, nullable=True),
    Column("attrs", JSONB, nullable=True),  # owner attribute corrections (align-wearhouse-outfit-recommender)
    Column("updated_at", TS, nullable=False, server_default=NOW),
    ForeignKeyConstraint(["size_system", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_wardrobe_item_state_size_value"),
    CheckConstraint("care_state IN ('ready', 'laundry', 'repair', 'stored')", name="care_state"),
    CheckConstraint("slot_override IS NULL OR slot_override " + SLOT_CHECK, name="slot_override"),
)

wardrobe_shelf = Table(
    "wardrobe_shelf", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    UniqueConstraint("user_id", "name"),
    CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="name"),
)

wardrobe_shelf_item = Table(
    "wardrobe_shelf_item", metadata,
    Column("shelf_id", UUID(as_uuid=True), ForeignKey("wardrobe_shelf.id"), primary_key=True),
    Column("item_id", UUID(as_uuid=True), primary_key=True),
    Column("position", Integer, nullable=False),
)

look = Table(
    "look", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("current_revision_no", Integer, nullable=False),
    Column("deleted_at", TS, nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="name"),
    Index("ix_look_user", "user_id", "created_at"),
)

look_revision = Table(
    "look_revision", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("look_id", UUID(as_uuid=True), ForeignKey("look.id"), nullable=False),
    Column("revision_no", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("slots", JSONB, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    UniqueConstraint("look_id", "revision_no"),
)

plan_entry = Table(
    "plan_entry", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("plan_date", Date, primary_key=True),
    Column("look_revision_id", UUID(as_uuid=True), ForeignKey("look_revision.id"), nullable=False),
    Column("occasion", Text, nullable=True),
    Column("note", Text, nullable=True),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("occasion IS NULL OR occasion IN ('casual', 'work', 'formal', 'sport', 'event')", name="occasion"),
    CheckConstraint("note IS NULL OR char_length(note) <= 200", name="note"),
)

wear_entry = Table(
    "wear_entry", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("worn_on", Date, nullable=False),
    Column("look_revision_id", UUID(as_uuid=True), ForeignKey("look_revision.id"), nullable=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Index("ix_wear_entry_user_date", "user_id", "worn_on"),
)

wear_entry_item = Table(
    "wear_entry_item", metadata,
    Column("wear_id", UUID(as_uuid=True), ForeignKey("wear_entry.id"), primary_key=True),
    Column("item_id", UUID(as_uuid=True), primary_key=True),
)
