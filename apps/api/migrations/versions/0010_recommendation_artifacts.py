"""Recommendation artifacts: versioned research outputs for serving and their item neighbour lists

Revision ID: 0010_recommendation_artifacts
Revises: 0009_object_management
Create Date: 2026-11-25
Forward-only (complete-wearhouse-research-intelligence). DDL from alembic autogenerate, reviewed; grants by hand.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0010_recommendation_artifacts'
down_revision = '0009_object_management'
branch_labels = None
depends_on = None

NEW_TABLES = ["recommendation_artifact", "item_neighbour"]


def upgrade() -> None:
    op.create_table('recommendation_artifact',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('version', sa.Text(), nullable=False),
    sa.Column('mode', sa.Text(), nullable=False),
    sa.Column('model_hash', sa.Text(), nullable=True),
    sa.Column('manifest', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('imported_by', sa.UUID(), nullable=True),
    sa.Column('imported_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('similar_items')", name=op.f('ck_recommendation_artifact_kind')),
    sa.CheckConstraint("mode <> 'trained' OR model_hash IS NOT NULL", name=op.f('ck_recommendation_artifact_trained_has_hash')),
    sa.CheckConstraint("mode IN ('trained', 'heuristic_baseline')", name=op.f('ck_recommendation_artifact_mode')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendation_artifact'))
    )
    op.create_index('uq_recommendation_artifact_active_kind', 'recommendation_artifact', ['kind'], unique=True, postgresql_where=sa.text('active'))
    op.create_table('item_neighbour',
    sa.Column('artifact_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('neighbour_id', sa.UUID(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['recommendation_artifact.id'], name=op.f('fk_item_neighbour_artifact_id_recommendation_artifact')),
    sa.ForeignKeyConstraint(['neighbour_id'], ['product.id'], name=op.f('fk_item_neighbour_neighbour_id_product')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_item_neighbour_product_id_product')),
    sa.PrimaryKeyConstraint('artifact_id', 'product_id', 'rank', name=op.f('pk_item_neighbour'))
    )
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
