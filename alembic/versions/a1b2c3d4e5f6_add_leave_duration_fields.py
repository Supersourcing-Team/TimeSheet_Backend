"""Add leave duration fields to leave_requests

Revision ID: a1b2c3d4e5f6
Revises: c05bdb83aee9
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "c05bdb83aee9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leave_requests", sa.Column("leave_duration_type", sa.String(20), nullable=True))
    op.add_column("leave_requests", sa.Column("half_day_period", sa.String(10), nullable=True))
    op.add_column("leave_requests", sa.Column("partial_start_time", sa.String(5), nullable=True))
    op.add_column("leave_requests", sa.Column("partial_end_time", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("leave_requests", "partial_end_time")
    op.drop_column("leave_requests", "partial_start_time")
    op.drop_column("leave_requests", "half_day_period")
    op.drop_column("leave_requests", "leave_duration_type")
