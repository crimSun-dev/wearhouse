"""Outfit recommendation runs, deduplicated exposures and choices; owner attribute corrections on wardrobe items

Revision ID: 0014_recommendation_runs
Revises: 0013_account_settings
Create Date: 2026-11-26
Forward-only (align-wearhouse-outfit-recommender). Hand-written; tests/test_migrations.py checks it against metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0014_recommendation_runs'
down_revision = '0013_account_settings'
branch_labels = None
depends_on = None

TS = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table('recommendation_run',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('displayed_at', TS, nullable=True),
    sa.Column('created_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_recommendation_run_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendation_run'))
    )
    op.create_index('ix_recommendation_run_user_created', 'recommendation_run', ['user_id', 'created_at'], unique=False)
    op.create_table('recommendation_exposure',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['recommendation_run.id'], name=op.f('fk_recommendation_exposure_run_id_recommendation_run')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_recommendation_exposure_user_id_app_user')),
    sa.PrimaryKeyConstraint('run_id', 'item_id', name=op.f('pk_recommendation_exposure'))
    )
    op.create_index('ix_recommendation_exposure_user_item', 'recommendation_exposure', ['user_id', 'item_id'], unique=False)
    op.create_table('recommendation_choice',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('suggestion_index', sa.Integer(), nullable=False),
    sa.Column('item_ids', postgresql.ARRAY(sa.UUID()), nullable=False),
    sa.Column('chosen_at', TS, nullable=False),
    sa.CheckConstraint('suggestion_index >= 0', name=op.f('ck_recommendation_choice_index_non_negative')),
    sa.ForeignKeyConstraint(['run_id'], ['recommendation_run.id'], name=op.f('fk_recommendation_choice_run_id_recommendation_run')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_recommendation_choice_user_id_app_user')),
    sa.PrimaryKeyConstraint('run_id', name=op.f('pk_recommendation_choice'))
    )
    op.create_index('ix_recommendation_choice_user', 'recommendation_choice', ['user_id'], unique=False)
    op.add_column('wardrobe_item_state', sa.Column('attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    grant_runtime(op.get_bind(), ["recommendation_run", "recommendation_exposure", "recommendation_choice"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
