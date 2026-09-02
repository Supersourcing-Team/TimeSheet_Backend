"""seed_default_roles_and_admin_user

Revision ID: a1b2c3d4e5f6
Revises: 817be71453d0
Create Date: 2026-09-02 17:31:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import os
from dotenv import load_dotenv


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '817be71453d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Load .env to read ADMIN_EMAIL
    load_dotenv()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@yourcompany.com")

    # ---------------------------------------------------------
    # 1. Seed default roles (idempotent – skip if they exist)
    # ---------------------------------------------------------
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )

    # Check-and-insert each role using a connection
    conn = op.get_bind()

    default_roles = [
        {"id": 1, "name": "Admin", "description": "Full system access – manages users, projects, and settings"},
        {"id": 2, "name": "Project_Manager", "description": "Manages projects, approves timesheets and weekend work requests"},
        {"id": 3, "name": "Account_Manager", "description": "Manages client accounts, views reports and project financials"},
        {"id": 4, "name": "Employee", "description": "Submits timesheets and leave requests"},
    ]

    for role in default_roles:
        exists = conn.execute(
            sa.text("SELECT 1 FROM roles WHERE name = :name"),
            {"name": role["name"]},
        ).fetchone()
        if not exists:
            conn.execute(
                roles_table.insert().values(**role)
            )

    # ---------------------------------------------------------
    # 2. Seed the first admin user from ADMIN_EMAIL (idempotent)
    # ---------------------------------------------------------
    admin_exists = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :email"),
        {"email": admin_email},
    ).fetchone()

    if not admin_exists:
        # Derive a display name from the email prefix
        email_prefix = admin_email.split("@")[0]
        first_name = email_prefix.capitalize()

        users_table = sa.table(
            "users",
            sa.column("id", sa.Integer),
            sa.column("role_id", sa.Integer),
            sa.column("employee_id", sa.String),
            sa.column("first_name", sa.String),
            sa.column("last_name", sa.String),
            sa.column("email", sa.String),
            sa.column("status", sa.String),
        )

        conn.execute(
            users_table.insert().values(
                role_id=1,  # Admin role
                employee_id="ADMIN-001",
                first_name=first_name,
                last_name="Admin",
                email=admin_email,
                status="Active",
            )
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Load .env to read ADMIN_EMAIL for targeted deletion
    load_dotenv()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@yourcompany.com")

    # Remove the seeded admin user
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email AND employee_id = 'ADMIN-001'"),
        {"email": admin_email},
    )

    # Remove the seeded roles
    conn.execute(sa.text("DELETE FROM roles WHERE name IN ('Admin', 'Project_Manager', 'Account_Manager', 'Employee')"))
