from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schema import LeaveReportSummary, TimesheetReportSummary


class ReportService:
    """Service generating aggregated report analytics and summaries."""

    @staticmethod
    async def generate_timesheet_report(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_id: Optional[int] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_billable: Optional[bool] = None,
    ) -> TimesheetReportSummary:
        role_name = getattr(current_user.role, "name", None)

        # If Project_Manager, filter by projects managed by PM unless Admin/Account_Manager
        pm_filter_id = None
        if role_name == "Project_Manager":
            pm_filter_id = current_user.id

        items = await ReportRepository.get_timesheet_report_data(
            db,
            start_date=start_date,
            end_date=end_date,
            project_id=project_id,
            client_id=client_id,
            user_id=user_id,
            is_billable=is_billable,
            pm_user_id=pm_filter_id,
        )

        total_hours = sum((item.billable_hours + item.non_billable_hours) for item in items)
        billable_hours = sum(item.billable_hours for item in items)
        non_billable_hours = sum(item.non_billable_hours for item in items)


        return TimesheetReportSummary(
            start_date=start_date,
            end_date=end_date,
            total_hours=total_hours,
            billable_hours=billable_hours,
            non_billable_hours=non_billable_hours,
            total_entries=len(items),
            items=items,
        )

    @staticmethod
    async def generate_leave_report(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
        leave_type_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> LeaveReportSummary:
        items = await ReportRepository.get_leave_report_data(
            db,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            leave_type_id=leave_type_id,
            status=status,
        )

        approved_count = sum(1 for item in items if item.status == "Approved")
        pending_count = sum(1 for item in items if item.status == "Pending")
        rejected_count = sum(1 for item in items if item.status == "Rejected")

        return LeaveReportSummary(
            start_date=start_date,
            end_date=end_date,
            total_requests=len(items),
            approved_requests=approved_count,
            pending_requests=pending_count,
            rejected_requests=rejected_count,
            items=items,
        )
