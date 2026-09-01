"""Consolidated full schema — single source of truth

Revision ID: 0001_consolidated_schema
Revises:
Create Date: 2026-09-01

This single migration replaces all previous incremental migrations.
It contains the complete, up-to-date schema for all tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_consolidated_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # roles
    # -----------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # -----------------------------------------------------------------------
    # users
    # -----------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("joining_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notifications_cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_employee_id"), "users", ["employee_id"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # clients
    # -----------------------------------------------------------------------
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # projects
    # -----------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("project_manager_id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("hourly_rate", sa.Float(), nullable=True),
        sa.Column("allocated_hours", sa.Float(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Planning"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["project_manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_project_name"), "projects", ["project_name"], unique=True)

    # -----------------------------------------------------------------------
    # project_assignments
    # -----------------------------------------------------------------------
    op.create_table(
        "project_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user_assignment"),
    )
    op.create_index(op.f("ix_project_assignments_id"), "project_assignments", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # timesheets
    # -----------------------------------------------------------------------
    op.create_table(
        "timesheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_assignment_id", sa.Integer(), nullable=False),
        sa.Column("timesheet_date", sa.Date(), nullable=False),
        sa.Column("billable_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("billable_work_summary", sa.Text(), nullable=True),
        sa.Column("non_billable_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("non_billable_work_summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="submitted",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_assignment_id"], ["project_assignments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "project_assignment_id", "timesheet_date", name="uq_user_project_date"
        ),
    )
    op.create_index(op.f("ix_timesheets_id"), "timesheets", ["id"], unique=False)
    op.create_index(op.f("ix_timesheets_timesheet_date"), "timesheets", ["timesheet_date"], unique=False)
    op.create_index(op.f("ix_timesheets_status"), "timesheets", ["status"], unique=False)

    # -----------------------------------------------------------------------
    # tools
    # -----------------------------------------------------------------------
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("cost_per_month", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tools_id"), "tools", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # tool_allocations
    # -----------------------------------------------------------------------
    op.create_table(
        "tool_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("allocation_date", sa.Date(), nullable=False),
        sa.Column("deallocation_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_allocations_id"), "tool_allocations", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # weekend_work_requests
    # -----------------------------------------------------------------------
    op.create_table(
        "weekend_work_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_assignment_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("planned_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Pending"),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_assignment_id"], ["project_assignments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weekend_work_requests_id"), "weekend_work_requests", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # holidays
    # -----------------------------------------------------------------------
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False, server_default="National"),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_holidays_id"), "holidays", ["id"], unique=False)
    op.create_index(op.f("ix_holidays_date"), "holidays", ["date"], unique=False)

    # -----------------------------------------------------------------------
    # leave_types
    # -----------------------------------------------------------------------
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("days_per_year", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocated_hours", sa.Integer(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("requires_document", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leave_types_id"), "leave_types", ["id"], unique=False)
    op.create_index(op.f("ix_leave_types_name"), "leave_types", ["name"], unique=True)
    op.create_index(op.f("ix_leave_types_code"), "leave_types", ["code"], unique=True)

    # -----------------------------------------------------------------------
    # leave_balances
    # -----------------------------------------------------------------------
    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("allocated_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("used_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "leave_type_id", "year", name="uq_user_leave_type_year"),
    )
    op.create_index(op.f("ix_leave_balances_id"), "leave_balances", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # leave_requests
    # -----------------------------------------------------------------------
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Pending"),
        sa.Column("managers_user_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("leave_duration_type", sa.String(length=20), nullable=True),
        sa.Column("half_day_period", sa.String(length=10), nullable=True),
        sa.Column("partial_start_time", sa.String(length=5), nullable=True),
        sa.Column("partial_end_time", sa.String(length=5), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
        sa.ForeignKeyConstraint(["managers_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leave_requests_id"), "leave_requests", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # working_calendar
    # -----------------------------------------------------------------------
    op.create_table(
        "working_calendar",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_day_hours", sa.Float(), nullable=False, server_default="8.0"),
        sa.Column("half_day_hours", sa.Float(), nullable=False, server_default="4.0"),
        sa.Column("partial_day_min_hours", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("partial_day_max_hours", sa.Float(), nullable=False, server_default="7.5"),
        sa.Column("working_days", sa.JSON(), nullable=False),
        sa.Column("time_zone", sa.String(), nullable=False, server_default="UTC"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_working_calendar_id"), "working_calendar", ["id"], unique=False)

    # -----------------------------------------------------------------------
    # system_settings
    # -----------------------------------------------------------------------
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_name", sa.String(length=255), nullable=False, server_default="SuperTime Enterprise"),
        sa.Column("org_reg_id", sa.String(length=100), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=False, server_default="admin@supertime.com"),
        sa.Column("company_logo_url", sa.String(length=500), nullable=True),
        sa.Column("time_zone", sa.String(length=100), nullable=False, server_default="Asia/Kolkata (IST UTC+05:30)"),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("timesheet_approval_reminders", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("leave_request_alerts", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("primary_color", sa.String(length=20), nullable=False, server_default="#2563eb"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_settings_id"), "system_settings", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("working_calendar")
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("leave_types")
    op.drop_table("holidays")
    op.drop_table("weekend_work_requests")
    op.drop_table("tool_allocations")
    op.drop_table("tools")
    op.drop_table("timesheets")
    op.drop_table("project_assignments")
    op.drop_table("projects")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("roles")
