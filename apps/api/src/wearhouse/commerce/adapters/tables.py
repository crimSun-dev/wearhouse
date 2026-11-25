"""add-wearhouse-sandbox-commerce (0006): sandbox offers, wishlist, cart and orders. No real money anywhere."""
from __future__ import annotations

from sqlalchemy import (BigInteger, CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, Integer, Table,
                        Text, text)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from ...platform.db import metadata

TS = TIMESTAMP(timezone=True)
NOW = text("now()")

sandbox_offer = Table(
    "sandbox_offer", metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    Column("price_idr", BigInteger, nullable=False),
    Column("currency", Text, nullable=False, server_default=text("'IDR'")),
    Column("stock", Integer, nullable=False),
    Column("updated_by", UUID(as_uuid=True), nullable=False),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("price_idr BETWEEN 1 AND 100000000", name="price"),
    CheckConstraint("currency = 'IDR'", name="currency"),
    CheckConstraint("stock BETWEEN 0 AND 100000", name="stock"),
)

wishlist_item = Table(
    "wishlist_item", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Index("ix_wishlist_item_user_created", "user_id", "created_at"),
)

cart_line = Table(
    "cart_line", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True),
    # one-size lines use '' (never exposed: the API shows null) so the size can be part of the key (add-wearhouse-sizes D5)
    Column("size_code", Text, primary_key=True, server_default=text("''")),
    Column("size_system", Text, nullable=False, server_default=text("''")),
    Column("quantity", Integer, nullable=False),
    Column("updated_at", TS, nullable=False, server_default=NOW),
    CheckConstraint("quantity BETWEEN 1 AND 5", name="quantity"),
    CheckConstraint("(size_code = '') = (size_system = '')", name="size_pair"),
)

sandbox_order = Table(
    "sandbox_order", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("status", Text, nullable=False),
    Column("currency", Text, nullable=False),
    Column("total_idr", BigInteger, nullable=False),
    Column("payment_ref", Text, nullable=False),
    Column("created_at", TS, nullable=False, server_default=NOW),
    Column("cancelled_at", TS, nullable=True),
    CheckConstraint("status IN ('fulfilled', 'cancelled')", name="status"),
    CheckConstraint("total_idr >= 0", name="total"),
    CheckConstraint("starts_with(payment_ref, 'sandbox-')", name="sandbox_payment"),
    Index("ix_sandbox_order_user_created", "user_id", "created_at", "id"),
)

sandbox_order_line = Table(
    "sandbox_order_line", metadata,
    Column("order_id", UUID(as_uuid=True), ForeignKey("sandbox_order.id"), primary_key=True),
    Column("line_no", Integer, primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("product.id"), nullable=False),
    Column("revision_id", UUID(as_uuid=True), ForeignKey("product_revision.id"), nullable=False),
    Column("product_name", Text, nullable=False),
    Column("unit_price_idr", BigInteger, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("size_system", Text, nullable=True),
    Column("size_code", Text, nullable=True),
    Column("size_label", Text, nullable=True),
    CheckConstraint("quantity BETWEEN 1 AND 5", name="quantity"),
    ForeignKeyConstraint(["size_system", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_sandbox_order_line_size_value"),
)

sandbox_order_unit = Table(
    "sandbox_order_unit", metadata,
    Column("unit_id", UUID(as_uuid=True), ForeignKey("garment_unit.id"), primary_key=True),
    Column("order_id", UUID(as_uuid=True), ForeignKey("sandbox_order.id"), nullable=False),
    Column("line_no", Integer, nullable=False),
    Column("delivery_id", UUID(as_uuid=True), ForeignKey("issuance_delivery.id"), nullable=True),
    Index("ix_sandbox_order_unit_order", "order_id", "line_no"),
)

sandbox_offer_size = Table(
    "sandbox_offer_size", metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("sandbox_offer.product_id", ondelete="CASCADE"),
           primary_key=True),
    Column("size_code", Text, primary_key=True),
    Column("size_system", Text, nullable=False),
    Column("stock", Integer, nullable=False),
    ForeignKeyConstraint(["size_system", "size_code"], ["size_value.system_code", "size_value.code"],
                         name="fk_sandbox_offer_size_size_value"),
    CheckConstraint("stock BETWEEN 0 AND 100000", name="stock"),
)
