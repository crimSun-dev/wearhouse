"""Wardrobe planning: declared items, item state, shelves, looks/revisions, plans, wear log, weather cache

Revision ID: 0007_wardrobe_planning
Revises: 0006_sandbox_commerce
Create Date: 2026-11-25
Forward-only (build-wearhouse-wardrobe-planning-services). DDL from alembic autogenerate, reviewed; grants added
by hand (look_revision has no UPDATE grant: revisions are immutable).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0007_wardrobe_planning'
down_revision = '0006_sandbox_commerce'
branch_labels = None
depends_on = None

NEW_TABLES = ["wardrobe_declared_item", "wardrobe_item_state", "wardrobe_shelf", "wardrobe_shelf_item", "look",
              "look_revision", "plan_entry", "wear_entry", "wear_entry_item", "weather_cache", "user_weather_location"]


def upgrade() -> None:
    op.create_table('weather_cache',
    sa.Column('adm4', sa.Text(), nullable=False),
    sa.Column('slots', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('fetched_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('fresh_until', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('adm4', name=op.f('pk_weather_cache'))
    )
    op.create_table('look',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('current_revision_no', sa.Integer(), nullable=False),
    sa.Column('deleted_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(name) BETWEEN 1 AND 60', name=op.f('ck_look_name')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_look_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_look'))
    )
    op.create_index('ix_look_user', 'look', ['user_id', 'created_at'], unique=False)
    op.create_table('user_weather_location',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('adm4', sa.Text(), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("adm4 ~ '^\\d{2}\\.\\d{2}\\.\\d{2}\\.\\d{4}$'", name=op.f('ck_user_weather_location_adm4')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_user_weather_location_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_user_weather_location'))
    )
    op.create_table('wardrobe_declared_item',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('slot', sa.Text(), nullable=False),
    sa.Column('category', sa.Text(), nullable=True),
    sa.Column('colour', sa.Text(), nullable=True),
    sa.Column('photo', sa.LargeBinary(), nullable=True),
    sa.Column('photo_type', sa.Text(), nullable=True),
    sa.Column('photo_sha256', sa.Text(), nullable=True),
    sa.Column('archived_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("photo_type IS NULL OR photo_type IN ('image/jpeg', 'image/png', 'image/webp')", name=op.f('ck_wardrobe_declared_item_photo_type')),
    sa.CheckConstraint("slot IN ('top', 'outer', 'bottom', 'dress', 'footwear', 'accessory')", name=op.f('ck_wardrobe_declared_item_slot')),
    sa.CheckConstraint('char_length(name) BETWEEN 1 AND 80', name=op.f('ck_wardrobe_declared_item_name')),
    sa.CheckConstraint('photo IS NULL OR octet_length(photo) <= 2097152', name=op.f('ck_wardrobe_declared_item_photo_size')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_wardrobe_declared_item_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wardrobe_declared_item'))
    )
    op.create_index('ix_wardrobe_declared_item_user', 'wardrobe_declared_item', ['user_id', 'created_at'], unique=False)
    op.create_table('wardrobe_item_state',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('care_state', sa.Text(), server_default=sa.text("'ready'"), nullable=False),
    sa.Column('slot_override', sa.Text(), nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("care_state IN ('ready', 'laundry', 'repair', 'stored')", name=op.f('ck_wardrobe_item_state_care_state')),
    sa.CheckConstraint("slot_override IS NULL OR slot_override IN ('top', 'outer', 'bottom', 'dress', 'footwear', 'accessory')", name=op.f('ck_wardrobe_item_state_slot_override')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_wardrobe_item_state_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', 'item_id', name=op.f('pk_wardrobe_item_state'))
    )
    op.create_table('wardrobe_shelf',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(name) BETWEEN 1 AND 40', name=op.f('ck_wardrobe_shelf_name')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_wardrobe_shelf_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wardrobe_shelf')),
    sa.UniqueConstraint('user_id', 'name', name=op.f('uq_wardrobe_shelf_user_id_name'))
    )
    op.create_table('look_revision',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('look_id', sa.UUID(), nullable=False),
    sa.Column('revision_no', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('slots', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['look_id'], ['look.id'], name=op.f('fk_look_revision_look_id_look')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_look_revision')),
    sa.UniqueConstraint('look_id', 'revision_no', name=op.f('uq_look_revision_look_id_revision_no'))
    )
    op.create_table('wardrobe_shelf_item',
    sa.Column('shelf_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['shelf_id'], ['wardrobe_shelf.id'], name=op.f('fk_wardrobe_shelf_item_shelf_id_wardrobe_shelf')),
    sa.PrimaryKeyConstraint('shelf_id', 'item_id', name=op.f('pk_wardrobe_shelf_item'))
    )
    op.create_table('plan_entry',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('plan_date', sa.Date(), nullable=False),
    sa.Column('look_revision_id', sa.UUID(), nullable=False),
    sa.Column('occasion', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("occasion IS NULL OR occasion IN ('casual', 'work', 'formal', 'sport', 'event')", name=op.f('ck_plan_entry_occasion')),
    sa.CheckConstraint('note IS NULL OR char_length(note) <= 200', name=op.f('ck_plan_entry_note')),
    sa.ForeignKeyConstraint(['look_revision_id'], ['look_revision.id'], name=op.f('fk_plan_entry_look_revision_id_look_revision')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_plan_entry_user_id_app_user')),
    sa.PrimaryKeyConstraint('user_id', 'plan_date', name=op.f('pk_plan_entry'))
    )
    op.create_table('wear_entry',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('worn_on', sa.Date(), nullable=False),
    sa.Column('look_revision_id', sa.UUID(), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['look_revision_id'], ['look_revision.id'], name=op.f('fk_wear_entry_look_revision_id_look_revision')),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_wear_entry_user_id_app_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wear_entry'))
    )
    op.create_index('ix_wear_entry_user_date', 'wear_entry', ['user_id', 'worn_on'], unique=False)
    op.create_table('wear_entry_item',
    sa.Column('wear_id', sa.UUID(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['wear_id'], ['wear_entry.id'], name=op.f('fk_wear_entry_item_wear_id_wear_entry')),
    sa.PrimaryKeyConstraint('wear_id', 'item_id', name=op.f('pk_wear_entry_item'))
    )
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
