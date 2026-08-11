from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectAssignmentMinimal(BaseModel):
    id: int
    project_id: int
    user_id: int
    role: str
    assignment_status: str

    model_config = ConfigDict(from_attributes=True)


class TimesheetCreate(BaseModel):
    project_assignment_id: int
    timesheet_date: date
    hours: float = Field(..., gt=0, le=8.0, description="Hours worked (0 < hours <= 8.0)")
    is_billable: bool = True
    task_description: Optional[str] = None
    work_summary: str = Field(..., min_length=3, description="Summary of work performed")


class TimesheetUpdate(BaseModel):
    project_assignment_id: Optional[int] = None
    timesheet_date: Optional[date] = None
    hours: Optional[float] = Field(None, gt=0, le=8.0)
    is_billable: Optional[bool] = None
    task_description: Optional[str] = None
    work_summary: Optional[str] = Field(None, min_length=3)


class TimesheetResponse(BaseModel):
    id: int
    user_id: int
    project_assignment_id: int
    timesheet_date: date
    hours: float
    is_billable: bool
    task_description: Optional[str] = None
    work_summary: str
    created_at: datetime
    updated_at: datetime

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
