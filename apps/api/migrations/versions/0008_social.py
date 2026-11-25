"""Social: look shares, plan sharing setting, notification read marker, profile showcase

Revision ID: 0008_social
Revises: 0007_wardrobe_planning
Create Date: 2026-11-25
Forward-only (add-wearhouse-social-profile-services). DDL from alembic autogenerate, reviewed; grants added by hand.
Visibility is never stored: it is computed at read time from the accounts privacy/friendship/block policy.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0008_social'
down_revision = '0007_wardrobe_planning'
branch_labels = None
depends_on = None

NEW_TABLES = ["look_share", "plan_share_setting", "notification_state", "profile_showcase"]


def upgrade() -> None:
    op.create_table('notification_state',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('read_through', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_notification_state_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_notification_state'))
    )
    op.create_table('plan_share_setting',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('audience', sa.Text(), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("audience IN ('none', 'friends')", name=op.f('ck_plan_share_setting_audience')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_plan_share_setting_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_plan_share_setting'))
    )
    op.create_table('profile_showcase',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('headline', sa.Text(), nullable=True),
    sa.Column('accent', sa.Text(), server_default=sa.text("'plum'"), nullable=False),
    sa.Column('featured', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("accent IN ('plum', 'ivory', 'blush', 'noir', 'sage', 'sky')", name=op.f('ck_profile_showcase_accent')),
    sa.CheckConstraint('headline IS NULL OR char_length(headline) <= 80', name=op.f('ck_profile_showcase_headline')),
    sa.CheckConstraint('jsonb_array_length(featured) <= 3', name=op.f('ck_profile_showcase_featured_max')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_profile_showcase_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_profile_showcase'))
    )
    op.create_table('look_share',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('look_id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('audience', sa.Text(), nullable=False),
    sa.Column('caption', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("audience IN ('friends', 'public')", name=op.f('ck_look_share_audience')),
    sa.CheckConstraint('caption IS NULL OR char_length(caption) <= 140', name=op.f('ck_look_share_caption')),
    sa.ForeignKeyConstraint(['look_id'], ['look.id'], name=op.f('fk_look_share_look_id_look')),
    sa.ForeignKeyConstraint(['owner_id'], ['app_user.id'], name=op.f('fk_look_share_owner_id_app_user')),
    sa.ForeignKeyConstraint(['revision_id'], ['look_revision.id'], name=op.f('fk_look_share_revision_id_look_revision')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_look_share'))
    )
    op.create_index('ix_look_share_owner_created', 'look_share', ['owner_id', 'created_at', 'id'], unique=False)
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
