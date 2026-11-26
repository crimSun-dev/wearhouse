"""Underwear slot: H&M "Underwear" products get their own wardrobe slot, so the fitting-room avatar can swap its
default modest base layer for the underwear a member wears (owner request 2026-11-26).

Revision ID: 0016_underwear_slot
Revises: 0015_tdd_completion
Create Date: 2026-11-26
Forward-only. Hand-written; tests/test_migrations.py checks it against metadata.
"""
from alembic import op

revision = '0016_underwear_slot'
down_revision = '0015_tdd_completion'
branch_labels = None
depends_on = None

SLOT_CHECK = ("IN ('top', 'outer', 'bottom', 'dress', 'footwear', 'underwear', 'bag', 'headwear', 'eyewear', 'earrings', "
              "'necklace', 'tie', 'scarf', 'belt', 'wrist', 'ring', 'accessory')")


def upgrade() -> None:
    op.drop_constraint(op.f('ck_wardrobe_declared_item_slot'), 'wardrobe_declared_item', type_='check')
    op.create_check_constraint(op.f('ck_wardrobe_declared_item_slot'), 'wardrobe_declared_item', 'slot ' + SLOT_CHECK)
    op.drop_constraint(op.f('ck_wardrobe_item_state_slot_override'), 'wardrobe_item_state', type_='check')
    op.create_check_constraint(op.f('ck_wardrobe_item_state_slot_override'), 'wardrobe_item_state',
                               'slot_override IS NULL OR slot_override ' + SLOT_CHECK)


def downgrade() -> None:
    raise NotImplementedError("forward-only migration")
