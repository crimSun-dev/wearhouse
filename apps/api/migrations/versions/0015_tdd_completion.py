"""TDD completion: accessory positions in slot constraints, sandbox revocation flags on owned items, share moderation
and reports, inspiration snapshots

Revision ID: 0015_tdd_completion
Revises: 0014_recommendation_runs
Create Date: 2026-11-26
Forward-only (complete-wearhouse-tdd). Hand-written; tests/test_migrations.py checks it against metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime, grant_runtime_columns

revision = '0015_tdd_completion'
down_revision = '0014_recommendation_runs'
branch_labels = None
depends_on = None

TS = postgresql.TIMESTAMP(timezone=True)
SLOT_CHECK = ("IN ('top', 'outer', 'bottom', 'dress', 'footwear', 'bag', 'headwear', 'eyewear', 'earrings', "
              "'necklace', 'tie', 'scarf', 'belt', 'wrist', 'ring', 'accessory')")


def upgrade() -> None:
    op.drop_constraint(op.f('ck_wardrobe_declared_item_slot'), 'wardrobe_declared_item', type_='check')
    op.create_check_constraint(op.f('ck_wardrobe_declared_item_slot'), 'wardrobe_declared_item', 'slot ' + SLOT_CHECK)
    op.drop_constraint(op.f('ck_wardrobe_item_state_slot_override'), 'wardrobe_item_state', type_='check')
    op.create_check_constraint(op.f('ck_wardrobe_item_state_slot_override'), 'wardrobe_item_state',
                               'slot_override IS NULL OR slot_override ' + SLOT_CHECK)

    op.drop_constraint(op.f('ck_role_grant_role'), 'role_grant', type_='check')
    op.create_check_constraint(op.f('ck_role_grant_role'), 'role_grant',
                               "role IN ('catalogue_editor', 'inventory_manager', 'moderator', 'admin')")

    op.add_column('owned_item', sa.Column('revoked_at', TS, nullable=True))
    op.add_column('owned_item', sa.Column('revoked_reason', sa.Text(), nullable=True))
    op.create_check_constraint(op.f('ck_owned_item_revoked_pair'), 'owned_item', '(revoked_at IS NULL) = (revoked_reason IS NULL)')

    op.add_column('look_share', sa.Column('moderation_state', sa.Text(), server_default=sa.text("'visible'"), nullable=False))
    op.add_column('look_share', sa.Column('moderated_by', sa.UUID(), nullable=True))
    op.add_column('look_share', sa.Column('moderated_at', TS, nullable=True))
    op.add_column('look_share', sa.Column('moderation_reason', sa.Text(), nullable=True))
    op.create_check_constraint(op.f('ck_look_share_moderation_state'), 'look_share', "moderation_state IN ('visible', 'hidden')")

    op.create_table('share_report',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('share_id', sa.UUID(), nullable=False),
    sa.Column('reporter_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default=sa.text("'open'"), nullable=False),
    sa.Column('created_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', TS, nullable=True),
    sa.CheckConstraint("status IN ('open', 'actioned', 'dismissed')", name=op.f('ck_share_report_status')),
    sa.CheckConstraint('char_length(reason) BETWEEN 1 AND 300', name=op.f('ck_share_report_reason')),
    sa.ForeignKeyConstraint(['reporter_id'], ['app_user.id'], name=op.f('fk_share_report_reporter_id_app_user')),
    sa.ForeignKeyConstraint(['share_id'], ['look_share.id'], name=op.f('fk_share_report_share_id_look_share')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_share_report')),
    sa.UniqueConstraint('share_id', 'reporter_id', name='uq_share_report_once')
    )
    op.create_index('ix_share_report_status_created', 'share_report', ['status', 'created_at'], unique=False)
    op.create_table('inspiration',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('source_share_id', sa.UUID(), nullable=True),
    sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_inspiration_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inspiration'))
    )
    op.create_index('ix_inspiration_user_created', 'inspiration', ['user_id', 'created_at'], unique=False)
    bind = op.get_bind()
    grant_runtime(bind, ["share_report", "inspiration"])
    grant_runtime_columns(bind, ["owned_item"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
