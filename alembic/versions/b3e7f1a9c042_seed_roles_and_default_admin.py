"""seed_roles_and_default_admin

Seeds the four system roles (Admin, Project_Manager, Account_Manager, Employee)
and creates a single default Admin user whose email is driven by the
ADMIN_EMAIL environment variable.

New developers only need to set ADMIN_EMAIL in their .env before running:

    alembic upgrade head

Revision ID: b3e7f1a9c042
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 11:20:00.000000

"""
from typing import Sequence, Union

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "b3e7f1a9c042"
down_revision: Union[str, None] = "0001_consolidated_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
SEED_ROLES = [
    {"name": "Admin",           "description": "System Administrator"},
    {"name": "Project_Manager", "description": "Project Manager"},
    {"name": "Account_Manager", "description": "Account Manager"},
    {"name": "Employee",        "description": "Software Engineer / Employee"},
]

# The admin email is read from the environment at migration time.
# Set ADMIN_EMAIL in your .env – this is the only value you need to change.
ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "admin@yourcompany.com")

DEFAULT_ADMIN = {
    "email":       ADMIN_EMAIL,
    "first_name":  "Admin",
    "last_name":   "User",
    "employee_id": "EMP-ADM-001",
    "status":      "Active",
}


# ---------------------------------------------------------------------------
# Upgrade: insert roles + default admin
# ---------------------------------------------------------------------------
def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Seed Roles (skip if already present)
    # ------------------------------------------------------------------
    for role in SEED_ROLES:
        existing = conn.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": role["name"]},
        ).fetchone()

        if not existing:
            conn.execute(
                text(
                    "INSERT INTO roles (name, description) "
                    "VALUES (:name, :description)"
                ),
                {"name": role["name"], "description": role["description"]},
            )

    # ------------------------------------------------------------------
    # 2. Resolve Admin role id
    # ------------------------------------------------------------------
    admin_role = conn.execute(
        text("SELECT id FROM roles WHERE name = 'Admin'")
    ).fetchone()

    if not admin_role:
        raise RuntimeError(
            "Admin role was not found after seeding – something went wrong."
        )
    admin_role_id = admin_role[0]

    # ------------------------------------------------------------------
    # 3. Seed default Admin user (skip if email already exists)
    # ------------------------------------------------------------------
    admin_email = DEFAULT_ADMIN["email"]

    if admin_email == "admin@yourcompany.com":
        import warnings
        warnings.warn(
            "\n[seed migration] ADMIN_EMAIL is still the placeholder value.\n"
            "Set ADMIN_EMAIL in your .env to your real work email and re-run "
            "the migration (alembic downgrade -1 && alembic upgrade head).",
            stacklevel=2,
        )

    existing_user = conn.execute(
        text(
            "SELECT id FROM users WHERE email = :email OR employee_id = :employee_id"
        ),
        {"email": admin_email, "employee_id": DEFAULT_ADMIN["employee_id"]},
    ).fetchone()

    if not existing_user:
        conn.execute(
            text(
                "INSERT INTO users "
                "  (email, first_name, last_name, employee_id, role_id, status) "
                "VALUES "
                "  (:email, :first_name, :last_name, :employee_id, :role_id, :status)"
            ),
            {
                "email":       DEFAULT_ADMIN["email"],
                "first_name":  DEFAULT_ADMIN["first_name"],
                "last_name":   DEFAULT_ADMIN["last_name"],
                "employee_id": DEFAULT_ADMIN["employee_id"],
                "role_id":     admin_role_id,
                "status":      DEFAULT_ADMIN["status"],
            },
        )


# ---------------------------------------------------------------------------
# Downgrade: remove ONLY the seeded admin user (leave roles intact –
# other users may depend on them)
# ---------------------------------------------------------------------------
def downgrade() -> None:
    conn = op.get_bind()

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@yourcompany.com")

    # Remove the default admin user if they were created by this migration
    conn.execute(
        text(
            "DELETE FROM users "
            "WHERE email = :email AND employee_id = 'EMP-ADM-001'"
        ),
        {"email": admin_email},
    )

    # NOTE: Roles are intentionally NOT removed on downgrade because other
    # users added during onboarding will already reference them.
