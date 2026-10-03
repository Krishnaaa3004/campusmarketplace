"""add product requests

Revision ID: a8c36d19f7b2
Revises: f5a1c83d2e64
Create Date: 2026-10-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a8c36d19f7b2'
down_revision: Union[str, Sequence[str], None] = 'f5a1c83d2e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'product_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product', sa.String(length=70), nullable=False),
        sa.Column('description', sa.String(length=70), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_requests_user_id'), 'product_requests', ['user_id'])
    op.create_index(op.f('ix_product_requests_created_at'), 'product_requests', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_product_requests_created_at'), table_name='product_requests')
    op.drop_index(op.f('ix_product_requests_user_id'), table_name='product_requests')
    op.drop_table('product_requests')
