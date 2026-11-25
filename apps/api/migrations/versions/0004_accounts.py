"""Accounts: profiles, handle holds, privacy, friend requests, friendships, blocks; app_user revocation/tombstone

Revision ID: 0004_accounts
Revises: 0003_ownership
Create Date: 2026-11-25
Forward-only (add-wearhouse-accounts). DDL from alembic autogenerate of the v2 metadata, reviewed. Explicit steps
added by hand: widening the attempt_bucket scope CHECK (autogenerate does not compare CHECK constraints),
backfilling a default profile and privacy row for each existing live account, and least-privilege grants.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime, grant_runtime_columns

revision = '0004_accounts'
down_revision = '0003_ownership'
branch_labels = None
depends_on = None

ACCOUNT_TABLES = ["account_profile", "handle_hold", "privacy_setting", "friend_request", "friendship", "user_block"]


def upgrade() -> None:
    op.create_table('account_profile',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('handle', sa.Text(), nullable=True),
    sa.Column('display_name', sa.Text(), nullable=False),
    sa.Column('bio', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('avatar_kind', sa.Text(), server_default=sa.text("'preset'"), nullable=False),
    sa.Column('avatar_preset', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('handle_changed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(avatar_kind = 'preset' AND avatar_url IS NULL) OR (avatar_kind = 'provider' AND avatar_url IS NOT NULL AND avatar_url LIKE 'https://%%')", name=op.f('ck_account_profile_avatar')),
    sa.CheckConstraint("handle IS NULL OR handle ~ '^[a-z][a-z0-9_]{2,19}$'", name=op.f('ck_account_profile_handle_format')),
    sa.CheckConstraint('char_length(bio) <= 160', name=op.f('ck_account_profile_bio_length')),
    sa.CheckConstraint('char_length(display_name) BETWEEN 1 AND 32', name=op.f('ck_account_profile_display_name_length')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_account_profile_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_account_profile'))
    )
    op.create_index('uq_account_profile_handle', 'account_profile', ['handle'], unique=True)
    op.create_table('friend_request',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('from_user', sa.UUID(), nullable=False),
    sa.Column('to_user', sa.UUID(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('resolved_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'accepted', 'declined', 'cancelled')", name=op.f('ck_friend_request_status')),
    sa.CheckConstraint('from_user <> to_user', name=op.f('ck_friend_request_not_self')),
    sa.ForeignKeyConstraint(['from_user'], ['app_user.id'], name=op.f('fk_friend_request_from_user_app_user')),
    sa.ForeignKeyConstraint(['to_user'], ['app_user.id'], name=op.f('fk_friend_request_to_user_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_friend_request'))
    )
    op.create_index('ix_friend_request_incoming', 'friend_request', ['to_user', 'status', 'created_at', 'id'], unique=False)
    op.create_index('ix_friend_request_outgoing', 'friend_request', ['from_user', 'status', 'created_at', 'id'], unique=False)
    op.create_index('uq_friend_request_one_pending', 'friend_request', ['from_user', 'to_user'], unique=True, postgresql_where=sa.text("status = 'pending'"))
    op.create_table('friendship',
    sa.Column('user_low', sa.UUID(), nullable=False),
    sa.Column('user_high', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.CheckConstraint('user_low < user_high', name=op.f('ck_friendship_ordered_pair')),
    sa.ForeignKeyConstraint(['user_high'], ['app_user.id'], name=op.f('fk_friendship_user_high_app_user')),
    sa.ForeignKeyConstraint(['user_low'], ['app_user.id'], name=op.f('fk_friendship_user_low_app_user')),
    sa.PrimaryKeyConstraint('user_low', 'user_high', name=op.f('pk_friendship'))
    )
    op.create_index('ix_friendship_user_high', 'friendship', ['user_high'], unique=False)
    op.create_table('handle_hold',
    sa.Column('handle', sa.Text(), nullable=False),
    sa.Column('held_for', sa.UUID(), nullable=True),
    sa.Column('available_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['held_for'], ['app_user.id'], name=op.f('fk_handle_hold_held_for_app_user')),
    sa.PrimaryKeyConstraint('handle', name=op.f('pk_handle_hold'))
    )
    op.create_table('privacy_setting',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('profile', sa.Text(), server_default=sa.text("'public'"), nullable=False),
    sa.Column('wardrobe', sa.Text(), server_default=sa.text("'private'"), nullable=False),
    sa.Column('friends_list', sa.Text(), server_default=sa.text("'friends'"), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("friends_list IN ('public', 'friends', 'private')", name=op.f('ck_privacy_setting_friends_list')),
    sa.CheckConstraint("profile IN ('public', 'friends', 'private')", name=op.f('ck_privacy_setting_profile')),
    sa.CheckConstraint("wardrobe IN ('public', 'friends', 'private')", name=op.f('ck_privacy_setting_wardrobe')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_privacy_setting_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_privacy_setting'))
    )
    op.create_table('user_block',
    sa.Column('blocker', sa.UUID(), nullable=False),
    sa.Column('blocked', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.CheckConstraint('blocker <> blocked', name=op.f('ck_user_block_not_self')),
    sa.ForeignKeyConstraint(['blocked'], ['app_user.id'], name=op.f('fk_user_block_blocked_app_user')),
    sa.ForeignKeyConstraint(['blocker'], ['app_user.id'], name=op.f('fk_user_block_blocker_app_user')),
    sa.PrimaryKeyConstraint('blocker', 'blocked', name=op.f('pk_user_block'))
    )
    op.create_index('ix_user_block_blocked', 'user_block', ['blocked'], unique=False)
    op.add_column('app_user', sa.Column('tokens_not_before', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('app_user', sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.drop_constraint(op.f("ck_attempt_bucket_scope"), "attempt_bucket", type_="check")
    op.create_check_constraint(op.f("ck_attempt_bucket_scope"), "attempt_bucket",
                               "scope IN ('actor', 'ip', 'global', 'friend_request', 'export')")
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO account_profile (user_id, display_name) "
                         "SELECT id, 'Wearhouse user' FROM app_user WHERE deleted_at IS NULL"))
    bind.execute(sa.text("INSERT INTO privacy_setting (user_id) SELECT id FROM app_user WHERE deleted_at IS NULL"))
    grant_runtime(bind, ACCOUNT_TABLES + ["user_subject"])
    grant_runtime_columns(bind, ["app_user"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
