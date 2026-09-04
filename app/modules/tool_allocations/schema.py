from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class ToolAllocationCreate(BaseModel):
    project_id: int = Field(..., ge=1)
    tool_id: int = Field(..., ge=1)
    allocation_date: date
    allocation_basis: Literal["working_day", "calendar_day", "week", "month"] = "working_day"


class ToolAllocationUpdate(BaseModel):
    deallocation_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=20)
    allocation_basis: Optional[Literal["working_day", "calendar_day", "week", "month"]] = None


class ToolAllocationResponse(BaseModel):
    id: int
    project_id: int
    tool_id: int
    allocation_date: date
    deallocation_date: Optional[date] = None
    allocation_basis: str = "working_day"
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
