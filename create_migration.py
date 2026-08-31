import pathlib

content = (
    '"""Add leave duration fields to leave_requests\n\n'
    'Revision ID: a1b2c3d4e5f6\n'
    'Revises: c05bdb83aee9\n'
    'Create Date: 2026-08-31\n\n'
    '"""\n'
    'from alembic import op\n'
    'import sqlalchemy as sa\n\n'
    'revision = "a1b2c3d4e5f6"\n'
    'down_revision = "c05bdb83aee9"\n'
    'branch_labels = None\n'
    'depends_on = None\n\n\n'
    'def upgrade() -> None:\n'
    '    op.add_column("leave_requests", sa.Column("leave_duration_type", sa.String(20), nullable=True))\n'
    '    op.add_column("leave_requests", sa.Column("half_day_period", sa.String(10), nullable=True))\n'
    '    op.add_column("leave_requests", sa.Column("partial_start_time", sa.String(5), nullable=True))\n'
    '    op.add_column("leave_requests", sa.Column("partial_end_time", sa.String(5), nullable=True))\n\n\n'
    'def downgrade() -> None:\n'
    '    op.drop_column("leave_requests", "partial_end_time")\n'
    '    op.drop_column("leave_requests", "partial_start_time")\n'
    '    op.drop_column("leave_requests", "half_day_period")\n'
    '    op.drop_column("leave_requests", "leave_duration_type")\n'
)

p = pathlib.Path("alembic/versions/a1b2c3d4e5f6_add_leave_duration_fields.py")
p.write_text(content, encoding="utf-8")
print("Done:", p)
