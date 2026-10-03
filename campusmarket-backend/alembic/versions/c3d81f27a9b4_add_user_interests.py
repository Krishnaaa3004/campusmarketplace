"""add user interests

Revision ID: c3d81f27a9b4
Revises: ac0ed39bf47e
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d81f27a9b4'
down_revision: Union[str, Sequence[str], None] = 'ac0ed39bf47e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default fills existing users with an empty list so NOT NULL is safe.
    op.add_column(
        'users',
        sa.Column('interests', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'interests')
