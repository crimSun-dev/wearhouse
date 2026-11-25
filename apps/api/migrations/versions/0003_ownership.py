"""Ownership: units, credentials, encrypted deliveries, owned items, ownership events

Revision ID: 0003_ownership
Revises: 0002_catalogue
Create Date: 2026-11-25
Forward-only. Written for this change from the v2 table metadata (alembic autogenerate output, then reviewed),
plus explicit environment-marker, immutability and least-privilege grant steps.
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import check_role_name, grant_runtime, make_immutable

revision = '0003_ownership'
down_revision = '0002_catalogue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('garment_unit',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('acquisition_revision_id', sa.UUID(), nullable=False),
    sa.Column('public_serial', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('issued_by', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('claimed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("public_serial ~ '^[a-z2-7]{26}$'", name=op.f('ck_garment_unit_public_serial')),
    sa.CheckConstraint("status IN ('issued', 'claimed', 'retired')", name=op.f('ck_garment_unit_status')),
    sa.ForeignKeyConstraint(['acquisition_revision_id'], ['product_revision.id'], name=op.f('fk_garment_unit_acquisition_revision_id_product_revision')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_garment_unit_product_id_product')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_garment_unit')),
    sa.UniqueConstraint('public_serial', name=op.f('uq_garment_unit_public_serial'))
    )
    op.create_table('activation_credential',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('unit_id', sa.UUID(), nullable=False),
    sa.Column('key_digest', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('audience_user_id', sa.UUID(), nullable=True),
    sa.Column('issued_by', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('redeemed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('revoked_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name=op.f('ck_activation_credential_key_digest')),
    sa.CheckConstraint("status IN ('active', 'redeemed', 'revoked')", name=op.f('ck_activation_credential_status')),
    sa.ForeignKeyConstraint(['audience_user_id'], ['app_user.id'], name=op.f('fk_activation_credential_audience_user_id_app_user')),
    sa.ForeignKeyConstraint(['unit_id'], ['garment_unit.id'], name=op.f('fk_activation_credential_unit_id_garment_unit')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_activation_credential')),
    sa.UniqueConstraint('key_digest', name=op.f('uq_activation_credential_key_digest'))
    )
    op.create_index('uq_activation_credential_one_active_per_unit', 'activation_credential', ['unit_id'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('issuance_delivery',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('unit_id', sa.UUID(), nullable=False),
    sa.Column('credential_id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('key_id', sa.Text(), nullable=True),
    sa.Column('nonce', sa.LargeBinary(), nullable=True),
    sa.Column('ciphertext', sa.LargeBinary(), nullable=True),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('erased_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('erase_reason', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('erased_at IS NULL OR (ciphertext IS NULL AND nonce IS NULL)', name=op.f('ck_issuance_delivery_erased_has_no_secret')),
    sa.ForeignKeyConstraint(['credential_id'], ['activation_credential.id'], name=op.f('fk_issuance_delivery_credential_id_activation_credential')),
    sa.ForeignKeyConstraint(['unit_id'], ['garment_unit.id'], name=op.f('fk_issuance_delivery_unit_id_garment_unit')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_issuance_delivery')),
    sa.UniqueConstraint('credential_id', name=op.f('uq_issuance_delivery_credential_id'))
    )
    op.create_table('owned_item',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('unit_id', sa.UUID(), nullable=False),
    sa.Column('acquisition_revision_id', sa.UUID(), nullable=False),
    sa.Column('presentation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('claimed_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['acquisition_revision_id'], ['product_revision.id'], name=op.f('fk_owned_item_acquisition_revision_id_product_revision')),
    sa.ForeignKeyConstraint(['unit_id'], ['garment_unit.id'], name=op.f('fk_owned_item_unit_id_garment_unit')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_owned_item_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_owned_item')),
    sa.UniqueConstraint('unit_id', name=op.f('uq_owned_item_unit_id'))
    )
    op.create_index('ix_owned_item_user_page', 'owned_item', ['user_id', 'created_at', 'id'], unique=False)
    op.create_table('ownership_event',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('unit_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('event_type', sa.Text(), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['owned_item.id'], name=op.f('fk_ownership_event_item_id_owned_item')),
    sa.ForeignKeyConstraint(['unit_id'], ['garment_unit.id'], name=op.f('fk_ownership_event_unit_id_garment_unit')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ownership_event'))
    )
    grant_runtime(op.get_bind(), ["garment_unit", "activation_credential", "issuance_delivery", "owned_item",
                                  "ownership_event"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
