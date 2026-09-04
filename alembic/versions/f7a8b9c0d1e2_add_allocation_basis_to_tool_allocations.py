"""add allocation_basis to tool_allocations

Revision ID: f7a8b9c0d1e2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add allocation_basis to tool_allocations with default 'working_day'
    op.add_column(
        "tool_allocations",
        sa.Column("allocation_basis", sa.String(20), nullable=False, server_default="working_day"),
    )


def downgrade() -> None:
    op.drop_column("tool_allocations", "allocation_basis")
