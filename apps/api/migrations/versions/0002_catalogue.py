"""Catalogue: sources, snapshots, products, immutable revisions, variants, media references

Revision ID: 0002_catalogue
Revises: 0001_platform_identity
Create Date: 2026-11-25
Forward-only. Written for this change from the v2 table metadata (alembic autogenerate output, then reviewed),
plus explicit environment-marker, immutability and least-privilege grant steps.
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import check_role_name, grant_runtime, make_immutable

revision = '0002_catalogue'
down_revision = '0001_platform_identity'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('catalogue_source',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('namespace', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("namespace ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f('ck_catalogue_source_namespace')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_catalogue_source')),
    sa.UniqueConstraint('namespace', name=op.f('uq_catalogue_source_namespace'))
    )
    op.create_table('source_snapshot',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('sha256', sa.Text(), nullable=False),
    sa.Column('file_name', sa.Text(), nullable=False),
    sa.Column('acquired_on', sa.Date(), nullable=False),
    sa.Column('permission', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_source_snapshot_sha256')),
    sa.ForeignKeyConstraint(['source_id'], ['catalogue_source.id'], name=op.f('fk_source_snapshot_source_id_catalogue_source')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_snapshot')),
    sa.UniqueConstraint('source_id', 'sha256', name=op.f('uq_source_snapshot_source_id_sha256'))
    )
    op.create_table('product',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=False),
    sa.Column('gtin', sa.Text(), nullable=True),
    sa.Column('gtin_scheme', sa.Text(), nullable=True),
    sa.Column('gtin_evidence', sa.Text(), nullable=True),
    sa.Column('catalogue_status', sa.Text(), server_default=sa.text("'active'"), nullable=False),
    sa.Column('current_revision_id', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("catalogue_status IN ('active', 'retired')", name=op.f('ck_product_catalogue_status')),
    sa.CheckConstraint('(gtin IS NULL AND gtin_scheme IS NULL AND gtin_evidence IS NULL) OR (gtin IS NOT NULL AND gtin_scheme IS NOT NULL AND gtin_evidence IS NOT NULL)', name=op.f('ck_product_gtin_evidence')),
    sa.ForeignKeyConstraint(['source_id'], ['catalogue_source.id'], name=op.f('fk_product_source_id_catalogue_source')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product')),
    sa.UniqueConstraint('source_id', 'external_id', name=op.f('uq_product_source_id_external_id'))
    )
    op.create_table('product_revision',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('revision_no', sa.Integer(), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('content_digest', sa.Text(), nullable=False),
    sa.Column('original_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('facts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('annotations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('revision_no >= 1', name=op.f('ck_product_revision_revision_no')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_product_revision_product_id_product')),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshot.id'], name=op.f('fk_product_revision_snapshot_id_source_snapshot')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_revision')),
    sa.UniqueConstraint('product_id', 'revision_no', name=op.f('uq_product_revision_product_id_revision_no'))
    )
    op.create_table('product_variant',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('variant_key', sa.Text(), nullable=False),
    sa.Column('facts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['revision_id'], ['product_revision.id'], name=op.f('fk_product_variant_revision_id_product_revision')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_variant')),
    sa.UniqueConstraint('revision_id', 'variant_key', name=op.f('uq_product_variant_revision_id_variant_key'))
    )
    op.create_table('media_reference',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('uri', sa.Text(), nullable=False),
    sa.Column('media_version', sa.Text(), nullable=False),
    sa.Column('rights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['revision_id'], ['product_revision.id'], name=op.f('fk_media_reference_revision_id_product_revision')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_media_reference')),
    sa.UniqueConstraint('revision_id', 'uri', 'media_version', name=op.f('uq_media_reference_revision_id_uri_media_version'))
    )
    op.create_foreign_key("fk_product_current_revision_id_product_revision", "product", "product_revision",
                          ["current_revision_id"], ["id"])
    bind = op.get_bind()
    make_immutable(bind, "product_revision")
    grant_runtime(bind, ["catalogue_source", "source_snapshot", "product", "product_revision", "product_variant",
                         "media_reference"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
