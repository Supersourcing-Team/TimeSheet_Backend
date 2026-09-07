from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserMinimal(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    employee_id: str

    model_config = ConfigDict(from_attributes=True)


class ProjectAssignmentMinimal(BaseModel):
    id: int
    project_id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class WeekendWorkSubmit(BaseModel):
    project_assignment_id: int
    work_date: date
    planned_hours: Optional[float] = Field(None, description="Total planned hours")
    billable_hours: float = Field(0.0, ge=0, description="Billable hours worked")
    billable_work_summary: Optional[str] = Field(None, description="Billable work notes")
    non_billable_hours: float = Field(0.0, ge=0, description="Non-billable hours worked")
    non_billable_work_summary: Optional[str] = Field(None, description="Non-billable work notes")
    reason: str = Field(..., min_length=3, description="Reason / deliverable objective")


class WeekendWorkCreate(BaseModel):
    project_assignment_id: int = Field(..., ge=1)
    work_date: date
    planned_hours: float = 0.0
    billable_hours: float = 0.0
    billable_work_summary: Optional[str] = None
    non_billable_hours: float = 0.0
    non_billable_work_summary: Optional[str] = None
    reason: str = Field(..., min_length=1, max_length=500)


class WeekendWorkReview(BaseModel):
    rejection_reason: Optional[str] = Field(None, description="Optional feedback or rejection reason")


class WeekendWorkResponse(BaseModel):
    id: int
    project_assignment_id: int
    work_date: date
    planned_hours: float = 0.0
    billable_hours: float = 0.0
    billable_work_summary: Optional[str] = None
    non_billable_hours: float = 0.0
    non_billable_work_summary: Optional[str] = None
    reason: str
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    project_assignment: Optional[ProjectAssignmentMinimal] = None
    approver: Optional[UserMinimal] = None

    model_config = ConfigDict(from_attributes=True)

