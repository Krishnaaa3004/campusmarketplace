"""add resources and resource access

Revision ID: b4f7e2a9c815
Revises: a8c36d19f7b2
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b4f7e2a9c815'
down_revision: Union[str, Sequence[str], None] = 'a8c36d19f7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'resources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('subject', sa.String(length=60), nullable=False),
        sa.Column('year', sa.String(length=3), nullable=False),
        sa.Column('copy_type', sa.String(length=4), nullable=False),
        sa.Column('offer_type', sa.String(length=4), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('delivery', sa.String(length=5), nullable=True),
        sa.Column('drive_url', sa.String(length=500), nullable=True),
        sa.Column('pickup_spot', sa.String(length=120), nullable=True),
        sa.Column('upi_id', sa.String(length=100), nullable=True),
        sa.Column('file_name', sa.String(length=64), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('preview_pages', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resources_owner_id'), 'resources', ['owner_id'])
    op.create_index(op.f('ix_resources_subject'), 'resources', ['subject'])

    op.create_table(
        'resource_access',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_id', 'user_id', name='uq_resource_access_resource_user'),
    )
    op.create_index(op.f('ix_resource_access_resource_id'), 'resource_access', ['resource_id'])
    op.create_index(op.f('ix_resource_access_user_id'), 'resource_access', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_resource_access_user_id'), table_name='resource_access')
    op.drop_index(op.f('ix_resource_access_resource_id'), table_name='resource_access')
    op.drop_table('resource_access')
    op.drop_index(op.f('ix_resources_subject'), table_name='resources')
    op.drop_index(op.f('ix_resources_owner_id'), table_name='resources')
    op.drop_table('resources')
