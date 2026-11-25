"""Object management: product media objects, pg_trgm search index, published-only browse indexes

Revision ID: 0009_object_management
Revises: 0008_social
Create Date: 2026-11-25
Forward-only (add-wearhouse-object-management). DDL from alembic autogenerate, reviewed. Added by hand: the
pg_trgm extension (trusted; available on Neon) before the trigram index, and runtime grants.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0009_object_management'
down_revision = '0008_social'
branch_labels = None
depends_on = None

NEW_TABLES = ["product_media"]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('product_media',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('content_type', sa.Text(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('sha256', sa.Text(), nullable=False),
    sa.Column('byte_size', sa.BigInteger(), nullable=False),
    sa.Column('alt_text', sa.Text(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('rights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('generator', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), server_default=sa.text("'active'"), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('removed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("content_type IN ('image/svg+xml', 'image/png', 'image/jpeg', 'image/webp')", name=op.f('ck_product_media_content_type')),
    sa.CheckConstraint("kind = 'generated' OR content_type <> 'image/svg+xml'", name=op.f('ck_product_media_svg_only_generated')),
    sa.CheckConstraint("kind IN ('generated', 'uploaded')", name=op.f('ck_product_media_kind')),
    sa.CheckConstraint("status IN ('active', 'removed')", name=op.f('ck_product_media_status')),
    sa.CheckConstraint('alt_text IS NULL OR char_length(alt_text) <= 200', name=op.f('ck_product_media_alt_text')),
    sa.CheckConstraint('byte_size BETWEEN 1 AND 5242880', name=op.f('ck_product_media_byte_size')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_product_media_product_id_product')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_media'))
    )
    op.create_index('ix_product_media_product_active', 'product_media', ['product_id', 'position'], unique=False, postgresql_where=sa.text("status = 'active'"))
    op.create_index('ix_product_browse_text_trgm', 'product', ['browse_text'], unique=False, postgresql_using='gin', postgresql_ops={'browse_text': 'gin_trgm_ops'}, postgresql_where=sa.text("publication_state = 'published'"))
    op.create_index('ix_product_pub_category', 'product', ['browse_category'], unique=False, postgresql_where=sa.text("publication_state = 'published'"))
    op.create_index('ix_product_pub_colour', 'product', ['browse_colour'], unique=False, postgresql_where=sa.text("publication_state = 'published'"))
    op.create_index('ix_product_pub_slot', 'product', ['browse_slot'], unique=False, postgresql_where=sa.text("publication_state = 'published'"))
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
