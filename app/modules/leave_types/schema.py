from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LeaveTypeBase(BaseModel):
    name: str
    code: Optional[str] = "GENERAL"
    days_per_year: Optional[int] = 12
    is_paid: Optional[bool] = True
    requires_document: Optional[bool] = False
    description: Optional[str] = None
    is_active: bool = True



class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    days_per_year: Optional[int] = None
    is_paid: Optional[bool] = None
    requires_document: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LeaveTypeResponse(LeaveTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
