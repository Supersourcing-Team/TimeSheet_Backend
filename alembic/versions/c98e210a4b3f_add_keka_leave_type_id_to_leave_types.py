"""add_keka_leave_type_id_to_leave_types

Revision ID: c98e210a4b3f
Revises: 'b75dc7d0b7a7'
Create Date: 2026-09-29 11:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c98e210a4b3f'
down_revision: Union[str, None] = 'b75dc7d0b7a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leave_types', sa.Column('keka_leave_type_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_leave_types_keka_leave_type_id'), 'leave_types', ['keka_leave_type_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leave_types_keka_leave_type_id'), table_name='leave_types')
    op.drop_column('leave_types', 'keka_leave_type_id')
