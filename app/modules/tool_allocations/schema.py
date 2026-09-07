from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolAllocationCreate(BaseModel):
    project_id: int = Field(..., ge=1)
    tool_id: int = Field(..., ge=1)
    monthly_cost: float = Field(default=0.0, ge=0)
    seats: int = Field(default=1, ge=1)
    allocation_date: date
    deallocation_date: Optional[date] = None


class ToolAllocationUpdate(BaseModel):
    monthly_cost: Optional[float] = Field(None, ge=0)
    seats: Optional[int] = Field(None, ge=1)
    allocation_date: Optional[date] = None
    deallocation_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=20)


class ToolAllocationResponse(BaseModel):
    id: int
    project_id: int
    tool_id: int
    monthly_cost: float
    seats: int
    allocation_date: date
    deallocation_date: Optional[date] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

