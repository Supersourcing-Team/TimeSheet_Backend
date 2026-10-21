"""add_profile_and_job_fields_to_users

Revision ID: e2eb56a2865e
Revises: 'c98e210a4b3f'
Create Date: 2026-10-21 12:13:28.356523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2eb56a2865e'
down_revision: Union[str, None] = 'c98e210a4b3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('middle_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('mobile_number', sa.String(length=25), nullable=True))
    op.add_column('users', sa.Column('job_title', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('secondary_job_title', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('business_unit', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('nationality', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('legal_entity', sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'legal_entity')
    op.drop_column('users', 'location')
    op.drop_column('users', 'nationality')
    op.drop_column('users', 'date_of_birth')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'business_unit')
    op.drop_column('users', 'secondary_job_title')
    op.drop_column('users', 'job_title')
    op.drop_column('users', 'mobile_number')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'middle_name')
