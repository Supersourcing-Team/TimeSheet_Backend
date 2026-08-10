from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LeaveTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LeaveTypeResponse(LeaveTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
