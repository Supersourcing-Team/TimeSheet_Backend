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
    planned_hours: float = Field(..., gt=0, description="Planned hours for the weekend work")
    reason: str = Field(..., min_length=3, description="Reason for weekend work request")


class WeekendWorkReview(BaseModel):
    rejection_reason: Optional[str] = Field(None, description="Optional feedback or rejection reason")


class WeekendWorkResponse(BaseModel):
    id: int
    project_assignment_id: int
    work_date: date
    planned_hours: float
    reason: str
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    project_assignment: Optional[ProjectAssignmentMinimal] = None
    approver: Optional[UserMinimal] = None

    model_config = ConfigDict(from_attributes=True)
