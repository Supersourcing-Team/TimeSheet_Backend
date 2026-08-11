from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LeaveTypeMinimal(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserMinimal(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    employee_id: str

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestSubmit(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=3, description="Reason for leave request")


class LeaveRequestReview(BaseModel):
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if applicable")


class LeaveRequestResponse(BaseModel):
    id: int
    user_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str
    status: str
    managers_user_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    user: Optional[UserMinimal] = None
    leave_type: Optional[LeaveTypeMinimal] = None
    manager: Optional[UserMinimal] = None

    model_config = ConfigDict(from_attributes=True)
