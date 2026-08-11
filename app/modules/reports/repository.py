from datetime import date
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client
from app.models.leave_request import LeaveRequest
from app.models.leave_type import LeaveType
from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.timesheet import Timesheet
from app.models.user import User
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
                Timesheet.hours,
                Timesheet.is_billable,
                Timesheet.work_summary,
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
        if is_billable is not None:
            query = query.filter(Timesheet.is_billable == is_billable)
        if pm_user_id:
            query = query.filter(Project.project_manager_id == pm_user_id)

        query = query.order_by(Timesheet.timesheet_date.desc(), Timesheet.id.desc())
        result = await db.execute(query)
        rows = result.all()

        items = [
            TimesheetReportItem(
                timesheet_id=row.timesheet_id,
                timesheet_date=row.timesheet_date,
                hours=row.hours,
                is_billable=row.is_billable,
                work_summary=row.work_summary,
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
