"""add user account type

Revision ID: d7e4a91b5c20
Revises: c3d81f27a9b4
Create Date: 2026-10-03 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd7e4a91b5c20'
down_revision: Union[str, Sequence[str], None] = 'c3d81f27a9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('account_type', sa.String(), server_default='buyer', nullable=False),
    )
    # Anyone who already has listings keeps the ability to manage them.
    op.execute(
        "UPDATE users SET account_type = 'seller' "
        "WHERE id IN (SELECT DISTINCT owner_id FROM listings)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'account_type')
