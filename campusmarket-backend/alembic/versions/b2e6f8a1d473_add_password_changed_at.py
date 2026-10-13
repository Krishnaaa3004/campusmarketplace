"""add users.password_changed_at (log out older sessions on password change)

Revision ID: b2e6f8a1d473
Revises: a7d3e5f9c104
Create Date: 2026-10-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2e6f8a1d473'
down_revision: Union[str, Sequence[str], None] = 'a7d3e5f9c104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'password_changed_at')
