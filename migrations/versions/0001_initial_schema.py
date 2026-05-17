"""Initial schema — creates all tables, indexes, and constraints.

Revision ID: 0001
Revises:
Create Date: 2026-05-12
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('full_name', sa.String(length=120), nullable=True),
        sa.Column('phone_number', sa.String(length=30), nullable=True),
        sa.Column('department', sa.String(length=80), nullable=True),
        sa.Column('job_title', sa.String(length=80), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True, server_default=sa.text("'inspector'")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_users_role_active', 'users', ['role', 'is_active'])
    op.create_index('ix_users_email', 'users', ['email'])

    # --- scans ---
    op.create_table(
        'scans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('name_normalized', sa.String(length=255), nullable=True),
        sa.Column('model_path', sa.String(length=500), nullable=True),
        sa.Column('source_upload_id', sa.String(length=120), nullable=True),
        sa.Column('scan_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('import_batch_id', sa.String(length=120), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_upload_id', name='uq_scans_source_upload_id'),
        sa.UniqueConstraint('scan_fingerprint', name='uq_scans_scan_fingerprint'),
    )
    op.create_index('ix_scans_name_normalized', 'scans', ['name_normalized'])
    op.create_index('ix_scans_import_batch_id', 'scans', ['import_batch_id'])
    op.create_index('ix_scans_assigned_to_user_id', 'scans', ['assigned_to_user_id'])

    # --- defects ---
    op.create_table(
        'defects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('z', sa.Float(), nullable=False),
        sa.Column('element', sa.String(length=255), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('defect_type', sa.String(length=50), nullable=True, server_default=sa.text("'Unknown'")),
        sa.Column('severity', sa.String(length=20), nullable=True, server_default=sa.text("'Medium'")),
        sa.Column('priority', sa.String(length=20), nullable=True, server_default=sa.text("'Medium'")),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default=sa.text("'Reported'")),
        sa.Column('image_path', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('source_defect_key', sa.String(length=160), nullable=True),
        sa.Column('coord_key', sa.String(length=200), nullable=True),
        sa.Column('import_batch_id', sa.String(length=120), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('is_manual', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scan_id', 'source_defect_key', name='uq_defects_scan_source_key'),
    )
    op.create_index('ix_defects_source_defect_key', 'defects', ['source_defect_key'])
    op.create_index('ix_defects_coord_key', 'defects', ['coord_key'])
    op.create_index('ix_defects_import_batch_id', 'defects', ['import_batch_id'])
    op.create_index('ix_defects_assigned_status', 'defects', ['assigned_to_user_id', 'status'])
    op.create_index('ix_defects_due_status', 'defects', ['due_date', 'status'])

    # --- activity_logs ---
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('defect_id', sa.Integer(), nullable=True),
        sa.Column('scan_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('old_value', sa.String(length=255), nullable=True),
        sa.Column('new_value', sa.String(length=255), nullable=True),
        sa.Column('event_uuid', sa.String(length=80), nullable=True),
        sa.Column('request_id', sa.String(length=80), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['defect_id'], ['defects.id'], ),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_uuid'),
    )
    op.create_index('ix_activity_logs_request_id', 'activity_logs', ['request_id'])


def downgrade() -> None:
    op.drop_table('activity_logs')
    op.drop_table('defects')
    op.drop_table('scans')
    op.drop_table('users')
