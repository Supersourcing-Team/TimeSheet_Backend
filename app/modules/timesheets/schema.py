from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectAssignmentMinimal(BaseModel):
    id: int
    project_id: int
    user_id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TimesheetCreate(BaseModel):
    project_assignment_id: int
    timesheet_date: date
    billable_hours: float = Field(0.0, ge=0, le=24.0, description="Billable hours worked")
    billable_work_summary: Optional[str] = Field(None, description="Summary of billable work")
    non_billable_hours: float = Field(0.0, ge=0, le=24.0, description="Non-billable hours worked")
    non_billable_work_summary: Optional[str] = Field(None, description="Summary of non-billable work")


class TimesheetUpdate(BaseModel):
    project_assignment_id: Optional[int] = None
    timesheet_date: Optional[date] = None
    billable_hours: Optional[float] = Field(None, ge=0, le=24.0)
    billable_work_summary: Optional[str] = None
    non_billable_hours: Optional[float] = Field(None, ge=0, le=24.0)
    non_billable_work_summary: Optional[str] = None


class TimesheetResponse(BaseModel):
    id: int
    user_id: int
    project_assignment_id: int
    timesheet_date: date
    billable_hours: float
    billable_work_summary: Optional[str] = None
    non_billable_hours: float
    non_billable_work_summary: Optional[str] = None
    status: str = "submitted"
    created_at: datetime
    updated_at: datetime

    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    project_name: Optional[str] = None

    project_assignment: Optional[ProjectAssignmentMinimal] = None

    model_config = ConfigDict(from_attributes=True)


class DailyTimesheetBreakdown(BaseModel):
    date: date
    total_hours: float
    entries: List[TimesheetResponse]


class WeeklyTimesheetSummary(BaseModel):
    start_date: date
    end_date: date
    total_weekly_hours: float
    daily_breakdowns: List[DailyTimesheetBreakdown]

