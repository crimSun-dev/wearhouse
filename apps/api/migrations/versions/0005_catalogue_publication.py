"""Catalogue publication: product publication pointer + browse columns, import jobs/rows, collections

Revision ID: 0005_catalogue_publication
Revises: 0004_accounts
Create Date: 2026-11-25
Forward-only (publish-wearhouse-catalogue). DDL from alembic autogenerate, reviewed. Added by hand: CHECK constraints
on product (autogenerate does not compare them), the backfill that publishes every existing active product at its
current revision (so issued units and the foundation thread keep working), and least-privilege grants.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0005_catalogue_publication'
down_revision = '0004_accounts'
branch_labels = None
depends_on = None

NEW_TABLES = ["catalogue_import_job", "catalogue_import_row", "catalogue_collection", "catalogue_collection_item"]
BACKFILL = """
UPDATE product p SET
    publication_state = CASE WHEN p.catalogue_status = 'retired' THEN 'retired' ELSE 'published' END,
    published_revision_id = p.current_revision_id,
    published_at = p.created_at,
    retired_at = CASE WHEN p.catalogue_status = 'retired' THEN now() END,
    browse_name = r.facts -> 'product_name' ->> 'value',
    browse_category = r.facts -> 'category' ->> 'value',
    browse_colour = r.facts -> 'colour' ->> 'value',
    browse_slot = r.annotations -> 'slot' ->> 'value',
    browse_text = lower(coalesce(r.facts -> 'product_name' ->> 'value', '') || ' ' ||
                        coalesce(r.facts -> 'description' ->> 'value', ''))
FROM product_revision r
WHERE r.id = p.current_revision_id
"""


def upgrade() -> None:
    op.create_table('catalogue_collection',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f('ck_catalogue_collection_slug')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_catalogue_collection')),
    sa.UniqueConstraint('slug', name=op.f('uq_catalogue_collection_slug'))
    )
    op.create_table('catalogue_collection_item',
    sa.Column('collection_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['catalogue_collection.id'], name=op.f('fk_catalogue_collection_item_collection_id_catalogue_collection')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_catalogue_collection_item_product_id_product')),
    sa.PrimaryKeyConstraint('collection_id', 'product_id', name=op.f('pk_catalogue_collection_item'))
    )
    op.create_table('catalogue_import_job',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('mapping_version', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('totals', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('running', 'completed')", name=op.f('ck_catalogue_import_job_status')),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshot.id'], name=op.f('fk_catalogue_import_job_snapshot_id_source_snapshot')),
    sa.ForeignKeyConstraint(['source_id'], ['catalogue_source.id'], name=op.f('fk_catalogue_import_job_source_id_catalogue_source')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_catalogue_import_job'))
    )
    op.create_table('catalogue_import_row',
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('row_no', sa.Integer(), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=True),
    sa.Column('outcome', sa.Text(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=True),
    sa.Column('revision_no', sa.Integer(), nullable=True),
    sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.CheckConstraint("outcome IN ('created', 'revised', 'unchanged', 'rejected')", name=op.f('ck_catalogue_import_row_outcome')),
    sa.ForeignKeyConstraint(['job_id'], ['catalogue_import_job.id'], name=op.f('fk_catalogue_import_row_job_id_catalogue_import_job')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_catalogue_import_row_product_id_product')),
    sa.PrimaryKeyConstraint('job_id', 'row_no', name=op.f('pk_catalogue_import_row'))
    )
    op.add_column('product', sa.Column('publication_state', sa.Text(), server_default=sa.text("'draft'"), nullable=False))
    op.add_column('product', sa.Column('published_revision_id', sa.UUID(), nullable=True))
    op.add_column('product', sa.Column('published_at', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('product', sa.Column('retired_at', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('product', sa.Column('browse_name', sa.Text(), nullable=True))
    op.add_column('product', sa.Column('browse_category', sa.Text(), nullable=True))
    op.add_column('product', sa.Column('browse_colour', sa.Text(), nullable=True))
    op.add_column('product', sa.Column('browse_slot', sa.Text(), nullable=True))
    op.add_column('product', sa.Column('browse_text', sa.Text(), nullable=True))
    op.create_index('ix_product_browse', 'product', ['publication_state', 'published_at', 'id'], unique=False)
    op.create_foreign_key('fk_product_published_revision_id_product_revision', 'product', 'product_revision', ['published_revision_id'], ['id'])
    op.create_check_constraint(op.f("ck_product_publication_state"), "product",
                               "publication_state IN ('draft', 'published', 'retired')")
    op.create_check_constraint(op.f("ck_product_published_has_revision"), "product",
                               "publication_state <> 'published' OR published_revision_id IS NOT NULL")
    bind = op.get_bind()
    bind.execute(sa.text(BACKFILL))
    grant_runtime(bind, NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
