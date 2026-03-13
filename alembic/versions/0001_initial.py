"""Initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('proteins', sa.Float(), nullable=True),
        sa.Column('carbs', sa.Float(), nullable=True),
        sa.Column('fats', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goals_id'), 'goals', ['id'], unique=False)

    op.create_table(
        'food_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('barcode', sa.String(), nullable=True),
        sa.Column('off_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('calories_100g', sa.Float(), nullable=True),
        sa.Column('proteins_100g', sa.Float(), nullable=True),
        sa.Column('carbs_100g', sa.Float(), nullable=True),
        sa.Column('fats_100g', sa.Float(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('cached_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('barcode'),
        sa.UniqueConstraint('off_id'),
    )
    op.create_index(op.f('ix_food_cache_id'), 'food_cache', ['id'], unique=False)
    op.create_index(op.f('ix_food_cache_barcode'), 'food_cache', ['barcode'], unique=True)
    op.create_index(op.f('ix_food_cache_off_id'), 'food_cache', ['off_id'], unique=True)

    op.create_table(
        'meal_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('logged_at', sa.DateTime(), nullable=True),
        sa.Column('food_name', sa.String(), nullable=False),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('quantity_g', sa.Float(), nullable=False),
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('proteins', sa.Float(), nullable=True),
        sa.Column('carbs', sa.Float(), nullable=True),
        sa.Column('fats', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('food_cache_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_meal_entries_id'), 'meal_entries', ['id'], unique=False)
    op.create_index(op.f('ix_meal_entries_date'), 'meal_entries', ['date'], unique=False)


def downgrade() -> None:
    op.drop_table('meal_entries')
    op.drop_table('food_cache')
    op.drop_table('goals')
