from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class LeaveMarkFromTimesheetRequest(BaseModel):
    """Payload for marking leave directly from the timesheet view."""
    leave_type_id: int
    leave_duration_type: str = Field(
        ..., description="One of: full_day, half_day, partial_day, multiple_days"
    )
    # For single-day leaves (full/half/partial)
    leave_date: Optional[date] = None
    # For multiple-day leaves
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    # Half-day sub-type
    half_day_period: Optional[str] = Field(
        None, description="'first' or 'second' — required for half_day"
    )
    # Partial-day time window (HH:MM 24h)
    partial_start_time: Optional[str] = Field(None, description="HH:MM e.g. '16:00'")
    partial_end_time: Optional[str] = Field(None, description="HH:MM e.g. '18:00'")
    reason: Optional[str] = "Marked from timesheet"

    @field_validator("leave_duration_type")
    @classmethod
    def validate_duration_type(cls, v: str) -> str:
        allowed = {"full_day", "half_day", "partial_day", "multiple_days"}
        if v not in allowed:
            raise ValueError(f"leave_duration_type must be one of {allowed}")
        return v

    @field_validator("half_day_period")
    @classmethod
    def validate_half_day_period(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"first", "second"}:
            raise ValueError("half_day_period must be 'first' or 'second'")
        return v


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
    # Duration fields (nullable for backward-compat with old records)
    leave_duration_type: Optional[str] = None
    half_day_period: Optional[str] = None
    partial_start_time: Optional[str] = None
    partial_end_time: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    user: Optional[UserMinimal] = None
    leave_type: Optional[LeaveTypeMinimal] = None
    manager: Optional[UserMinimal] = None

    model_config = ConfigDict(from_attributes=True)


class LeaveCheckDateResponse(BaseModel):
    """Returned by GET /leave-requests/check-date to tell the frontend the leave status for a date."""
    date: date
    has_leave: bool
    leave_duration_type: Optional[str] = None   # full_day | half_day | partial_day
    half_day_period: Optional[str] = None        # first | second
    partial_start_time: Optional[str] = None
    partial_end_time: Optional[str] = None
    leave_id: Optional[int] = None
    leave_type_name: Optional[str] = None
    # Derived fields for UI convenience
    available_hours: float = 8.0                 # hours available for timesheet on this date
    blocked_message: Optional[str] = None        # human-readable label, e.g. "On Leave – Full Day"

