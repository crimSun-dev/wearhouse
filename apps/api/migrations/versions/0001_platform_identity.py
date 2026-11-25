"""Platform (environment marker, idempotency, attempts, audit, outbox) and identity tables

Revision ID: 0001_platform_identity
Revises: 
Create Date: 2026-11-25
Forward-only. Written for this change from the v2 table metadata (alembic autogenerate output, then reviewed),
plus explicit environment-marker, immutability and least-privilege grant steps.
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import check_role_name, grant_runtime, make_immutable

revision = '0001_platform_identity'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    x = context.get_x_argument(as_dictionary=True)
    environment = x["environment"]
    role = x.get("runtime_role")
    if role:
        check_role_name(role)
    op.create_table('wearhouse_environment',
    sa.Column('id', sa.SmallInteger(), nullable=False),
    sa.Column('app_family', sa.Text(), nullable=False),
    sa.Column('environment', sa.Text(), nullable=False),
    sa.Column('runtime_role', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('id = 1', name=op.f('ck_wearhouse_environment_singleton')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wearhouse_environment'))
    )
    op.create_table('app_user',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_user'))
    )
    op.create_table('user_subject',
    sa.Column('issuer', sa.Text(), nullable=False),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_user_subject_user_id_app_user')),
    sa.PrimaryKeyConstraint('issuer', 'subject', name=op.f('pk_user_subject'))
    )
    op.create_index('ix_user_subject_user_id', 'user_subject', ['user_id'], unique=False)
    op.create_table('role_grant',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('granted_by', sa.Text(), nullable=False),
    sa.Column('granted_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('catalogue_editor', 'inventory_manager', 'admin')", name=op.f('ck_role_grant_role')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_role_grant_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', 'role', name=op.f('pk_role_grant'))
    )
    op.create_table('idempotency_record',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('route', sa.Text(), nullable=False),
    sa.Column('idem_key', sa.Text(), nullable=False),
    sa.Column('request_fingerprint', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('lease_token', sa.UUID(), nullable=True),
    sa.Column('lease_expires_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('attempt_reserved', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('response_status', sa.Integer(), nullable=True),
    sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.CheckConstraint("status <> 'completed' OR response_status IS NOT NULL", name=op.f('ck_idempotency_record_completed_has_response')),
    sa.CheckConstraint("status IN ('processing', 'completed')", name=op.f('ck_idempotency_record_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_record')),
    sa.UniqueConstraint('actor_id', 'route', 'idem_key', name=op.f('uq_idempotency_record_actor_id_route_idem_key'))
    )
    op.create_table('attempt_bucket',
    sa.Column('scope', sa.Text(), nullable=False),
    sa.Column('scope_key', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("scope IN ('actor', 'ip', 'global')", name=op.f('ck_attempt_bucket_scope')),
    sa.PrimaryKeyConstraint('scope', 'scope_key', name=op.f('pk_attempt_bucket'))
    )
    op.create_table('attempt_event',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('scope', sa.Text(), nullable=False),
    sa.Column('scope_key', sa.Text(), nullable=False),
    sa.Column('reserved_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('idempotency_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['scope', 'scope_key'], ['attempt_bucket.scope', 'attempt_bucket.scope_key'], name='fk_attempt_event_bucket'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attempt_event'))
    )
    op.create_index('ix_attempt_event_scope_window', 'attempt_event', ['scope', 'scope_key', 'reserved_at'], unique=False)
    op.create_table('audit_event',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('target_type', sa.Text(), nullable=False),
    sa.Column('target_id', sa.Text(), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('request_id', sa.Text(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_event'))
    )
    op.create_table('outbox_event',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.Text(), nullable=False),
    sa.Column('aggregate_type', sa.Text(), nullable=False),
    sa.Column('aggregate_id', sa.UUID(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('available_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('dispatched_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_event'))
    )
    op.create_index('ix_outbox_event_pending', 'outbox_event', ['dispatched_at', 'available_at'], unique=False)
    op.create_table('outbox_delivery',
    sa.Column('consumer', sa.Text(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('delivered_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['outbox_event.id'], name=op.f('fk_outbox_delivery_event_id_outbox_event')),
    sa.PrimaryKeyConstraint('consumer', 'event_id', name=op.f('pk_outbox_delivery'))
    )
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO wearhouse_environment (id, app_family, environment, runtime_role) "
                         "VALUES (1, 'wearhouse-v2', :env, :role)"), {"env": environment, "role": role})
    make_immutable(bind, "wearhouse_environment")
    grant_runtime(bind, ["wearhouse_environment", "alembic_version", "app_user", "user_subject", "role_grant",
                         "idempotency_record", "attempt_bucket", "attempt_event", "audit_event", "outbox_event",
                         "outbox_delivery"])


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
