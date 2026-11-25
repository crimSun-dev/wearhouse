"""SQLAlchemy models mirroring the TDD §3.2 DDL. One model set for Neon Postgres and SQLite."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SLOT_CHECK = "slot IN ('top','bottom','dress','outer','footwear','accessory')"
JSONType = JSON().with_variant(JSONB(), "postgresql")
BigId = BigInteger().with_variant(Integer(), "sqlite")  # SQLite only autoincrements INTEGER PRIMARY KEY


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything is stored in UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (CheckConstraint("gender IN ('female','male')", name="ck_user_gender"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str | None] = mapped_column(Text)
    home_adm4: Mapped[str | None] = mapped_column(Text)


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (CheckConstraint(SLOT_CHECK, name="ck_product_slot"),)
    gtin: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    color_hex: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(Text, nullable=False)
    rain_suitable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    heavy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    long_sleeve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    long_bottom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    formality: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    image_url: Mapped[str | None] = mapped_column(Text)
    glb_template: Mapped[str | None] = mapped_column(Text)

    def attrs(self) -> dict:
        return {
            "color_hex": self.color_hex, "style": self.style, "rain_suitable": self.rain_suitable,
            "heavy": self.heavy, "long_sleeve": self.long_sleeve, "long_bottom": self.long_bottom,
            "formality": self.formality,
        }


class GarmentCode(Base):
    __tablename__ = "garment_code"
    serial: Mapped[str] = mapped_column(Text, primary_key=True)  # public, 128-bit hex
    gtin: Mapped[str] = mapped_column(Text, ForeignKey("product.gtin"), nullable=False)
    activation_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # SHA-256 of the 80-bit code
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Garment(Base):
    __tablename__ = "garment"
    __table_args__ = (CheckConstraint(SLOT_CHECK, name="ck_garment_slot"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    gtin: Mapped[str | None] = mapped_column(Text, ForeignKey("product.gtin"))
    serial: Mapped[str | None] = mapped_column(Text, ForeignKey("garment_code.serial"), unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    times_recommended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    times_chosen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_worn_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Outfit(Base):
    __tablename__ = "outfit"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    planned_for: Mapped[date | None] = mapped_column(Date)
    occasion: Mapped[str | None] = mapped_column(Text)


class OutfitItem(Base):
    __tablename__ = "outfit_item"
    # PRIMARY KEY (outfit_id, slot): one item per slot, enforced by the database.
    outfit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("outfit.id", ondelete="CASCADE"), primary_key=True)
    slot: Mapped[str] = mapped_column(Text, primary_key=True)
    garment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("garment.id"), nullable=False)


class WearLog(Base):
    __tablename__ = "wear_log"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    outfit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("outfit.id", ondelete="CASCADE"))
    worn_on: Mapped[date] = mapped_column(Date, nullable=False)


class ActivationAttempt(Base):
    __tablename__ = "activation_attempt"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)  # ORM needs a key
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ok: Mapped[bool | None] = mapped_column(Boolean)


class InterfaceLog(Base):
    __tablename__ = "interface_log"
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    interface: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    weather_source: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
