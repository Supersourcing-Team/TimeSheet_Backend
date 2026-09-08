from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolAllocationCreate(BaseModel):
    project_id: int = Field(..., ge=1)
    tool_id: int = Field(..., ge=1)
    monthly_cost: float = Field(default=0.0, ge=0)
    seats: int = Field(default=1, ge=1)
    allocation_date: date
    deallocation_date: date = Field(..., description="Required end date of tool allocation")
    allocation_basis: Literal["working_day", "calendar_day", "week", "month"] = "working_day"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.deallocation_date < self.allocation_date:
            raise ValueError("End date (deallocation date) cannot be earlier than Start date (allocation date).")
        return self


class ToolAllocationUpdate(BaseModel):
    monthly_cost: Optional[float] = Field(None, ge=0)
    seats: Optional[int] = Field(None, ge=1)
    allocation_date: Optional[date] = None
    deallocation_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=20)
    allocation_basis: Optional[Literal["working_day", "calendar_day", "week", "month"]] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.allocation_date and self.deallocation_date:
            if self.deallocation_date < self.allocation_date:
                raise ValueError("End date (deallocation date) cannot be earlier than Start date (allocation date).")
        return self


class ToolAllocationResponse(BaseModel):
    id: int
    project_id: int
    tool_id: int
    monthly_cost: float
    seats: int
    allocation_date: date
    deallocation_date: Optional[date] = None
    allocation_basis: str = "working_day"
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
