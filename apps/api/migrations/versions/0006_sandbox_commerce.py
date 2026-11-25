"""Sandbox commerce: offers, wishlist, cart, orders, order lines, order units

Revision ID: 0006_sandbox_commerce
Revises: 0005_catalogue_publication
Create Date: 2026-11-25
Forward-only (add-wearhouse-sandbox-commerce). DDL from alembic autogenerate, reviewed; grants added by hand.
No real payment data exists anywhere: orders carry a 'sandbox-' payment reference enforced by a CHECK constraint.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0006_sandbox_commerce'
down_revision = '0005_catalogue_publication'
branch_labels = None
depends_on = None

NEW_TABLES = ["sandbox_offer", "wishlist_item", "cart_line", "sandbox_order", "sandbox_order_line",
              "sandbox_order_unit"]


def upgrade() -> None:
    op.create_table('sandbox_order',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('currency', sa.Text(), nullable=False),
    sa.Column('total_idr', sa.BigInteger(), nullable=False),
    sa.Column('payment_ref', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('cancelled_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("starts_with(payment_ref, 'sandbox-')", name=op.f('ck_sandbox_order_sandbox_payment')),
    sa.CheckConstraint("status IN ('fulfilled', 'cancelled')", name=op.f('ck_sandbox_order_status')),
    sa.CheckConstraint('total_idr >= 0', name=op.f('ck_sandbox_order_total')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_sandbox_order_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sandbox_order'))
    )
    op.create_index('ix_sandbox_order_user_created', 'sandbox_order', ['user_id', 'created_at', 'id'], unique=False)
    op.create_table('cart_line',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity BETWEEN 1 AND 5', name=op.f('ck_cart_line_quantity')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_cart_line_product_id_product')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_cart_line_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', 'product_id', name=op.f('pk_cart_line'))
    )
    op.create_table('sandbox_offer',
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('price_idr', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.Text(), server_default=sa.text("'IDR'"), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("currency = 'IDR'", name=op.f('ck_sandbox_offer_currency')),
    sa.CheckConstraint('price_idr BETWEEN 1 AND 100000000', name=op.f('ck_sandbox_offer_price')),
    sa.CheckConstraint('stock BETWEEN 0 AND 100000', name=op.f('ck_sandbox_offer_stock')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_sandbox_offer_product_id_product')),
    sa.PrimaryKeyConstraint('product_id', name=op.f('pk_sandbox_offer'))
    )
    op.create_table('wishlist_item',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_wishlist_item_product_id_product')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_wishlist_item_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', 'product_id', name=op.f('pk_wishlist_item'))
    )
    op.create_index('ix_wishlist_item_user_created', 'wishlist_item', ['user_id', 'created_at'], unique=False)
    op.create_table('sandbox_order_line',
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('product_name', sa.Text(), nullable=False),
    sa.Column('unit_price_idr', sa.BigInteger(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity BETWEEN 1 AND 5', name=op.f('ck_sandbox_order_line_quantity')),
    sa.ForeignKeyConstraint(['order_id'], ['sandbox_order.id'], name=op.f('fk_sandbox_order_line_order_id_sandbox_order')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_sandbox_order_line_product_id_product')),
    sa.ForeignKeyConstraint(['revision_id'], ['product_revision.id'], name=op.f('fk_sandbox_order_line_revision_id_product_revision')),
    sa.PrimaryKeyConstraint('order_id', 'line_no', name=op.f('pk_sandbox_order_line'))
    )
    op.create_table('sandbox_order_unit',
    sa.Column('unit_id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('delivery_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['delivery_id'], ['issuance_delivery.id'], name=op.f('fk_sandbox_order_unit_delivery_id_issuance_delivery')),
    sa.ForeignKeyConstraint(['order_id'], ['sandbox_order.id'], name=op.f('fk_sandbox_order_unit_order_id_sandbox_order')),
    sa.ForeignKeyConstraint(['unit_id'], ['garment_unit.id'], name=op.f('fk_sandbox_order_unit_unit_id_garment_unit')),
    sa.PrimaryKeyConstraint('unit_id', name=op.f('pk_sandbox_order_unit'))
    )
    op.create_index('ix_sandbox_order_unit_order', 'sandbox_order_unit', ['order_id', 'line_no'], unique=False)
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
