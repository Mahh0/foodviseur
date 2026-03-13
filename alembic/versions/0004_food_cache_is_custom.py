"""Add is_custom to food_cache

Revision ID: 0004
Revises: 0003
Create Date: 2025-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('food_cache',
        sa.Column('is_custom', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade():
    op.drop_column('food_cache', 'is_custom')
