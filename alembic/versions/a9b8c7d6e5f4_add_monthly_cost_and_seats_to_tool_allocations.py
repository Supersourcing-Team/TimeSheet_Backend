"""add_monthly_cost_and_seats_to_tool_allocations

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add monthly_cost and seats columns to tool_allocations
    # These exist in the ORM model but were missing from the DB
    op.add_column(
        "tool_allocations",
        sa.Column("monthly_cost", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "tool_allocations",
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("tool_allocations", "seats")
    op.drop_column("tool_allocations", "monthly_cost")
