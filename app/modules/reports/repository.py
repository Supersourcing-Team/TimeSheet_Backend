from datetime import date
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.clients.model import Client
from app.modules.leave_requests.model import LeaveRequest
from app.modules.leave_types.model import LeaveType
from app.modules.projects.model import Project
from app.modules.project_assignments.model import ProjectAssignment
from app.modules.timesheets.model import Timesheet
from app.modules.users.model import User
from app.modules.reports.schema import LeaveReportItem, TimesheetReportItem


class ReportRepository:
    """Repository executing reporting and analytics queries across domains."""

    @staticmethod
    async def get_timesheet_report_data(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_id: Optional[int] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_billable: Optional[bool] = None,
        pm_user_id: Optional[int] = None,
    ) -> List[TimesheetReportItem]:
        query = (
            select(
                Timesheet.id.label("timesheet_id"),
                Timesheet.timesheet_date,
                Timesheet.billable_hours,
                Timesheet.billable_work_summary,
                Timesheet.non_billable_hours,
                Timesheet.non_billable_work_summary,
                User.id.label("user_id"),
                (User.first_name + " " + User.last_name).label("user_name"),
                Project.id.label("project_id"),
                Project.project_name.label("project_name"),
                Client.id.label("client_id"),
                Client.name.label("client_name"),
            )
            .join(User, Timesheet.user_id == User.id)
            .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
            .join(Project, ProjectAssignment.project_id == Project.id)
            .join(Client, Project.client_id == Client.id)
        )

        if start_date:
            query = query.filter(Timesheet.timesheet_date >= start_date)
        if end_date:
            query = query.filter(Timesheet.timesheet_date <= end_date)
        if project_id:
            query = query.filter(Project.id == project_id)
        if client_id:
            query = query.filter(Client.id == client_id)
        if user_id:
            query = query.filter(User.id == user_id)
        # Filter by billable status is no longer a simple boolean since a row can have both.
        # If needed, we'd add logic here to filter where billable_hours > 0 or non_billable_hours > 0.
        if is_billable is True:
            query = query.filter(Timesheet.billable_hours > 0)
        elif is_billable is False:
            query = query.filter(Timesheet.non_billable_hours > 0)
        if pm_user_id:
            query = query.filter(Project.project_manager_id == pm_user_id)

        query = query.order_by(Timesheet.timesheet_date.desc(), Timesheet.id.desc())
        result = await db.execute(query)
        rows = result.all()

        items = [
            TimesheetReportItem(
                timesheet_id=row.timesheet_id,
                timesheet_date=row.timesheet_date,
                billable_hours=row.billable_hours,
                billable_work_summary=row.billable_work_summary,
                non_billable_hours=row.non_billable_hours,
                non_billable_work_summary=row.non_billable_work_summary,
                user_id=row.user_id,
                user_name=row.user_name,
                project_id=row.project_id,
                project_name=row.project_name,
                client_id=row.client_id,
                client_name=row.client_name,
            )
            for row in rows
        ]
        return items

    @staticmethod
    async def get_leave_report_data(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
        leave_type_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[LeaveReportItem]:
        query = (
            select(
                LeaveRequest.id.label("leave_request_id"),
                User.id.label("user_id"),
                (User.first_name + " " + User.last_name).label("user_name"),
                LeaveType.name.label("leave_type_name"),
                LeaveRequest.start_date,
                LeaveRequest.end_date,
                LeaveRequest.status,
                LeaveRequest.reason,
            )
            .join(User, LeaveRequest.user_id == User.id)
            .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
        )

        if start_date:
            query = query.filter(LeaveRequest.start_date >= start_date)
        if end_date:
            query = query.filter(LeaveRequest.end_date <= end_date)
        if user_id:
            query = query.filter(User.id == user_id)
        if leave_type_id:
            query = query.filter(LeaveRequest.leave_type_id == leave_type_id)
        if status:
            query = query.filter(LeaveRequest.status == status)

        query = query.order_by(LeaveRequest.start_date.desc(), LeaveRequest.id.desc())
        result = await db.execute(query)
        rows = result.all()

        items = [
            LeaveReportItem(
                leave_request_id=row.leave_request_id,
                user_id=row.user_id,
                user_name=row.user_name,
                leave_type_name=row.leave_type_name,
                start_date=row.start_date,
                end_date=row.end_date,
                status=row.status,
                reason=row.reason,
            )
            for row in rows
        ]
        return items
