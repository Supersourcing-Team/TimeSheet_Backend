from typing import List, Optional
from pydantic import BaseModel
from datetime import date

class TimesheetSummaryWidget(BaseModel):
    total_logged_hours: float
    billable_hours: float
    non_billable_hours: float
    target_weekly_hours: float

class ProjectSummaryWidget(BaseModel):
    active_projects_count: int
    primary_project_name: Optional[str]
    primary_project_code: Optional[str]

class LeaveBalanceWidget(BaseModel):
    annual_total: float
    annual_used: float
    annual_remaining: float
    sick_total: float
    sick_used: float
    sick_remaining: float

class RecentLeaveRequestWidget(BaseModel):
    id: int
    type: str
    start_date: date
    end_date: date
    days_count: float
    status: str

class UpcomingHolidayWidget(BaseModel):
    name: str
    date: date
    days_remaining: int

class DashboardSummaryResponse(BaseModel):
    timesheet_summary: TimesheetSummaryWidget
    project_summary: ProjectSummaryWidget
    leave_balance: LeaveBalanceWidget
    recent_leaves: List[RecentLeaveRequestWidget]
    upcoming_holiday: Optional[UpcomingHolidayWidget] = None
    role_overview: Optional[dict] = None
