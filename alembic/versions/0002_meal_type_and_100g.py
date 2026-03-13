"""Add meal_type and per-100g columns to meal_entries

Revision ID: 0002_meal_type_and_100g
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_meal_type_and_100g'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('meal_entries') as batch_op:
        batch_op.add_column(sa.Column('meal_type', sa.String(), nullable=True, server_default='dejeuner'))
        batch_op.add_column(sa.Column('calories_100g', sa.Float(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('proteins_100g', sa.Float(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('carbs_100g', sa.Float(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('fats_100g', sa.Float(), nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('meal_entries') as batch_op:
        batch_op.drop_column('meal_type')
        batch_op.drop_column('calories_100g')
        batch_op.drop_column('proteins_100g')
        batch_op.drop_column('carbs_100g')
        batch_op.drop_column('fats_100g')
