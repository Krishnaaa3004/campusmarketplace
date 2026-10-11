"""add password login: user password + lockout, OTP purpose + attempts

Revision ID: a7d3e5f9c104
Revises: f1c4b8d2e973
Create Date: 2026-10-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7d3e5f9c104'
down_revision: Union[str, Sequence[str], None] = 'f1c4b8d2e973'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: existing accounts keep working and are asked to create a password.
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('failed_logins', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('otp_codes', sa.Column('purpose', sa.String(length=10), server_default='login', nullable=False))
    op.add_column('otp_codes', sa.Column('attempts', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('otp_codes', 'attempts')
    op.drop_column('otp_codes', 'purpose')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_logins')
    op.drop_column('users', 'password_hash')
