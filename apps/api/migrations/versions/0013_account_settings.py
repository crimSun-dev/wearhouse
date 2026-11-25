"""Account settings: one versioned JSONB row of explicitly set preferences per user

Revision ID: 0013_account_settings
Revises: 0012_size_browse
Create Date: 2026-11-25
Forward-only (add-wearhouse-settings-security). The registry (keys, choices, defaults) lives in accounts/domain.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0013_account_settings'
down_revision = '0012_size_browse'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('account_setting',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('values', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('version', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('jsonb_typeof("values") = \'object\'', name=op.f('ck_account_setting_values_object')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_account_setting_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_account_setting'))
    )
    grant_runtime(op.get_bind(), ["account_setting"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
