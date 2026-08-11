from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class TimesheetReportItem(BaseModel):
    timesheet_id: int
    timesheet_date: date
    hours: float
    is_billable: bool
    work_summary: str
    user_id: int
    user_name: str
    project_id: int
    project_name: str
    client_id: int
    client_name: str

    model_config = ConfigDict(from_attributes=True)


class TimesheetReportSummary(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_hours: float
    billable_hours: float
    non_billable_hours: float
    total_entries: int
    items: List[TimesheetReportItem]


class LeaveReportItem(BaseModel):
    leave_request_id: int
    user_id: int
    user_name: str
    leave_type_name: str
    start_date: date
    end_date: date
    status: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class LeaveReportSummary(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_requests: int
    approved_requests: int
    pending_requests: int
    rejected_requests: int
    items: List[LeaveReportItem]
