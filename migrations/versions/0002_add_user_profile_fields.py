"""Add user profile fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-17
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(length=120), nullable=True))
    op.add_column('users', sa.Column('phone_number', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('job_title', sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'job_title')
    op.drop_column('users', 'department')
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'full_name')