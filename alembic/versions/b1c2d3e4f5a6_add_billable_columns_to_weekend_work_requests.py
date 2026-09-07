"""add_billable_columns_to_weekend_work_requests

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add billable/non-billable columns to weekend_work_requests
    # These exist in the ORM model but were missing from the DB schema
    op.add_column(
        "weekend_work_requests",
        sa.Column("billable_hours", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "weekend_work_requests",
        sa.Column("billable_work_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "weekend_work_requests",
        sa.Column("non_billable_hours", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "weekend_work_requests",
        sa.Column("non_billable_work_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weekend_work_requests", "non_billable_work_summary")
    op.drop_column("weekend_work_requests", "non_billable_hours")
    op.drop_column("weekend_work_requests", "billable_work_summary")
    op.drop_column("weekend_work_requests", "billable_hours")
