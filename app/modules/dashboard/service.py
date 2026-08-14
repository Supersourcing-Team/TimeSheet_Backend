from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, func

from app.models.user import User
from app.modules.dashboard.schema import (
    DashboardSummaryResponse,
    LeaveBalanceWidget,
    ProjectSummaryWidget,
    RecentLeaveRequestWidget,
    TimesheetSummaryWidget,
    UpcomingHolidayWidget,
)
from app.models.holiday import Holiday
from app.modules.holidays.repository import HolidayRepository
from app.modules.leave_balances.repository import LeaveBalanceRepository
from app.modules.leave_requests.repository import LeaveRequestRepository
from app.modules.project_assignments.repository import ProjectAssignmentRepository
from app.modules.timesheets.repository import TimesheetRepository
from app.models.project import Project
from app.models.leave_type import LeaveType
from app.models.leave_request import LeaveRequest


class DashboardService:
    @staticmethod
    async def get_summary(db: AsyncSession, current_user: User) -> DashboardSummaryResponse:
        today = date.today()
        # 1. Timesheet Summary
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        timesheet_entries = await TimesheetRepository.get_entries_in_range(
            db, user_id=current_user.id, start_date=start_of_week, end_date=end_of_week
        )
        
        total_logged = sum(entry.hours for entry in timesheet_entries)
        billable_logged = sum(entry.hours for entry in timesheet_entries if entry.is_billable)
        non_billable_logged = total_logged - billable_logged
        target_weekly_hours = 40.0
        
        timesheet_widget = TimesheetSummaryWidget(
            total_logged_hours=total_logged,
            billable_hours=billable_logged,
            non_billable_hours=non_billable_logged,
            target_weekly_hours=target_weekly_hours,
        )
        
        # 2. Project Summary
        assignments = await ProjectAssignmentRepository(db).get_by_user(current_user.id)
        active_projects = len(assignments)
        
        primary_project_name = None
        primary_project_code = None
        if active_projects > 0:
            res = await db.execute(select(Project).where(Project.id == assignments[0].project_id))
            proj = res.scalar_one_or_none()
            if proj:
                primary_project_name = proj.name
                primary_project_code = proj.project_code
                
        project_widget = ProjectSummaryWidget(
            active_projects_count=active_projects,
            primary_project_name=primary_project_name,
            primary_project_code=primary_project_code
        )
        
        # 3. Leave Balances
        year = today.year
        balances = await LeaveBalanceRepository.get_by_user_and_year(db, current_user.id, year)
        
        annual_total = 0.0
        annual_used = 0.0
        sick_total = 0.0
        sick_used = 0.0
        
        for bal in balances:
            res = await db.execute(select(LeaveType).where(LeaveType.id == bal.leave_type_id))
            lt = res.scalar_one_or_none()
            if lt:
                name_lower = lt.name.lower()
                if 'annual' in name_lower or 'earned' in name_lower or 'privilege' in name_lower or 'pl' in name_lower:
                    annual_total += bal.allocated_days
                    annual_used += bal.used_days
                elif 'sick' in name_lower or 'medical' in name_lower or 'sl' in name_lower:
                    sick_total += bal.allocated_days
                    sick_used += bal.used_days
                    
        leave_balance_widget = LeaveBalanceWidget(
            annual_total=annual_total,
            annual_used=annual_used,
            annual_remaining=annual_total - annual_used,
            sick_total=sick_total,
            sick_used=sick_used,
            sick_remaining=sick_total - sick_used
        )
        
        # 4. Recent Leave Requests
        requests, _ = await LeaveRequestRepository.list_by_user(
            db, user_id=current_user.id, page=1, limit=5
        )
        recent_leaves = []
        for req in requests:
            res = await db.execute(select(LeaveType).where(LeaveType.id == req.leave_type_id))
            lt = res.scalar_one_or_none()
            type_name = lt.name if lt else "Leave"
            
            recent_leaves.append(
                RecentLeaveRequestWidget(
                    id=req.id,
                    type=type_name,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    days_count=req.total_days,
                    status=req.status
                )
            )
            
        # 5. Upcoming Holiday
        res = await db.execute(select(Holiday).where(Holiday.date >= today).order_by(Holiday.date.asc()).limit(1))
        next_holiday = res.scalar_one_or_none()
        upcoming_holiday_widget = None
        if next_holiday:
            days_remaining = (next_holiday.date - today).days
            upcoming_holiday_widget = UpcomingHolidayWidget(
                name=next_holiday.name,
                date=next_holiday.date,
                days_remaining=days_remaining
            )
            
        # 6. Role Overview (Manager/Admin stats)
        role_overview = None
        admin_overview = None
        role_name = current_user.role.name if current_user.role else ""
        
        if role_name in ["Admin", "Project_Manager", "Account_Manager"]:
            role_overview = {
                "role": role_name,
                "team_pending_leaves": 0,
                "active_org_projects": 0
            }
            
            pending_res = await db.execute(
                select(func.count(LeaveRequest.id)).where(LeaveRequest.status == 'Pending')
            )
            role_overview["team_pending_leaves"] = pending_res.scalar() or 0
            
            active_proj_res = await db.execute(
                select(func.count(Project.id)).where(Project.status == 'Active')
            )
            role_overview["active_org_projects"] = active_proj_res.scalar() or 0
            
        if role_name == "Admin":
            active_users_res = await db.execute(
                select(func.count(User.id)).where(User.status == 'active')
            )
            active_users_count = active_users_res.scalar() or 0
            
            on_leave_users_res = await db.execute(
                select(func.count(User.id)).where(User.status == 'on_leave')
            )
            on_leave_users_count = on_leave_users_res.scalar() or 0
            
            from app.modules.dashboard.schema import AdminOverviewWidget
            admin_overview = AdminOverviewWidget(
                active_users_count=active_users_count,
                on_leave_users_count=on_leave_users_count,
                pending_leaves_count=role_overview.get("team_pending_leaves", 0) if role_overview else 0,
                active_projects_count=role_overview.get("active_org_projects", 0) if role_overview else 0,
            )

        return DashboardSummaryResponse(
            timesheet_summary=timesheet_widget,
            project_summary=project_widget,
            leave_balance=leave_balance_widget,
            recent_leaves=recent_leaves,
            upcoming_holiday=upcoming_holiday_widget,
            role_overview=role_overview,
            admin_overview=admin_overview
        )
