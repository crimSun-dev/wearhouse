"""Sizes: size systems and values (seeded commercial sizes), product sizes, usual sizes, per-size offer stock, and
size columns on cart lines, order lines, garment units and wardrobe item state

Revision ID: 0011_sizes
Revises: 0010_recommendation_artifacts
Create Date: 2026-11-25
Forward-only (add-wearhouse-sizes). Hand-written; tests/test_migrations.py checks it against the table metadata.
The seed rows are reference DATA: staff can add, rename, re-rank and retire them through the API.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from wearhouse.bootstrap.migration_helpers import grant_runtime

revision = '0011_sizes'
down_revision = '0010_recommendation_artifacts'
branch_labels = None
depends_on = None

NEW_TABLES = ["size_system", "size_value", "product_size", "user_size_preference", "sandbox_offer_size"]
TS = postgresql.TIMESTAMP(timezone=True)

SYSTEMS = [
    # code, label, position, default slots, sizes (code, label), common codes
    ("alpha", "Letter (international)", 10, ["top", "outer", "bottom", "dress"],
     ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL"], {"XS", "S", "M", "L", "XL", "XXL"}),
    ("eu_clothing", "EU clothing", 20, [],
     [str(n) for n in range(32, 54, 2)], {str(n) for n in range(34, 48, 2)}),
    ("eu_shoe", "EU shoe", 30, ["footwear"],
     [str(n) for n in range(35, 48)], {str(n) for n in range(36, 46)}),
]


def _size_fk(table: str, sys_col: str = "size_system", code_col: str = "size_code"):
    return sa.ForeignKeyConstraint([sys_col, code_col], ["size_value.system_code", "size_value.code"],
                                   name=f"fk_{table}_size_value")


def upgrade() -> None:
    op.create_table('size_system',
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('slots', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('updated_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]{1,31}$'", name=op.f('ck_size_system_code')),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_size_system'))
    )
    op.create_table('size_value',
    sa.Column('system_code', sa.Text(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('common', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('updated_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("code ~ '^[A-Za-z0-9.]{1,8}$'", name=op.f('ck_size_value_code')),
    sa.ForeignKeyConstraint(['system_code'], ['size_system.code'], name=op.f('fk_size_value_system_code_size_system')),
    sa.PrimaryKeyConstraint('system_code', 'code', name=op.f('pk_size_value'))
    )
    op.create_table('product_size',
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('system_code', sa.Text(), nullable=False),
    sa.Column('size_code', sa.Text(), nullable=False),
    sa.Column('origin', sa.Text(), nullable=False),
    sa.Column('created_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("origin IN ('rule', 'staff')", name=op.f('ck_product_size_origin')),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('fk_product_size_product_id_product')),
    _size_fk('product_size', 'system_code', 'size_code'),
    sa.PrimaryKeyConstraint('product_id', 'system_code', 'size_code', name=op.f('pk_product_size'))
    )
    op.create_index('ix_product_size_lookup', 'product_size', ['system_code', 'size_code', 'product_id'], unique=False)
    op.create_table('user_size_preference',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('system_code', sa.Text(), nullable=False),
    sa.Column('size_code', sa.Text(), nullable=False),
    sa.Column('updated_at', TS, server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], name=op.f('fk_user_size_preference_user_id_app_user')),
    _size_fk('user_size_preference', 'system_code', 'size_code'),
    sa.PrimaryKeyConstraint('user_id', 'system_code', name=op.f('pk_user_size_preference'))
    )
    op.create_table('sandbox_offer_size',
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('size_code', sa.Text(), nullable=False),
    sa.Column('size_system', sa.Text(), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.CheckConstraint('stock BETWEEN 0 AND 100000', name=op.f('ck_sandbox_offer_size_stock')),
    sa.ForeignKeyConstraint(['product_id'], ['sandbox_offer.product_id'], ondelete='CASCADE',
                            name=op.f('fk_sandbox_offer_size_product_id_sandbox_offer')),
    _size_fk('sandbox_offer_size'),
    sa.PrimaryKeyConstraint('product_id', 'size_code', name=op.f('pk_sandbox_offer_size'))
    )

    # cart_line: the size joins the key ('' = one size, never exposed)
    op.add_column('cart_line', sa.Column('size_code', sa.Text(), server_default=sa.text("''"), nullable=False))
    op.add_column('cart_line', sa.Column('size_system', sa.Text(), server_default=sa.text("''"), nullable=False))
    op.drop_constraint('pk_cart_line', 'cart_line', type_='primary')
    op.create_primary_key('pk_cart_line', 'cart_line', ['user_id', 'product_id', 'size_code'])
    op.create_check_constraint(op.f('ck_cart_line_size_pair'), 'cart_line', "(size_code = '') = (size_system = '')")

    for table, label in (('sandbox_order_line', True), ('garment_unit', True), ('wardrobe_item_state', False)):
        op.add_column(table, sa.Column('size_system', sa.Text(), nullable=True))
        op.add_column(table, sa.Column('size_code', sa.Text(), nullable=True))
        if label:
            op.add_column(table, sa.Column('size_label', sa.Text(), nullable=True))
        op.create_foreign_key(f'fk_{table}_size_value', table, 'size_value', ['size_system', 'size_code'],
                              ['system_code', 'code'])

    systems = sa.table('size_system', sa.column('code'), sa.column('label'), sa.column('position'),
                       sa.column('slots', postgresql.ARRAY(sa.Text())))
    values = sa.table('size_value', sa.column('system_code'), sa.column('code'), sa.column('label'),
                      sa.column('rank'), sa.column('common', sa.Boolean()))
    op.bulk_insert(systems, [{"code": c, "label": l, "position": p, "slots": s} for c, l, p, s, _, _ in SYSTEMS])
    op.bulk_insert(values, [{"system_code": c, "code": code, "label": code, "rank": (i + 1) * 10,
                             "common": code in common}
                            for c, _, _, _, sizes, common in SYSTEMS for i, code in enumerate(sizes)])
    grant_runtime(op.get_bind(), NEW_TABLES)


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
