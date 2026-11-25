"""Size browse: product.browse_sizes ('system:code' array, denormalised from product_size) with a GIN index

Revision ID: 0012_size_browse
Revises: 0011_sizes
Create Date: 2026-11-25
Forward-only (add-wearhouse-sizes). At 105k products an EXISTS over product_size made the planner read every matching
size row and sort (about 300 ms for a common size); an array on product lets it walk the newest-first index for common
sizes and use the GIN index for rare ones. product_size stays the source of truth; the repository keeps both in step.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0012_size_browse'
down_revision = '0011_sizes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('product', sa.Column('browse_sizes', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"),
                                       nullable=False))
    op.execute("""
        UPDATE product p SET browse_sizes = s.sizes
        FROM (SELECT product_id, array_agg(system_code || ':' || size_code) AS sizes
              FROM product_size GROUP BY product_id) s
        WHERE s.product_id = p.id
    """)
    op.create_index('ix_product_browse_sizes', 'product', ['browse_sizes'], unique=False, postgresql_using='gin',
                    postgresql_where=sa.text("publication_state = 'published'"))


def downgrade() -> None:
    raise RuntimeError("Wearhouse v2 migrations are forward-only; restore from backup instead.")
