from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LeaveBalanceBase(BaseModel):
    user_id: int
    leave_type_id: int
    year: int
    allocated_days: float = 0.0


class LeaveBalanceCreate(LeaveBalanceBase):
    pass


class LeaveBalanceUpdate(BaseModel):
    allocated_days: Optional[float] = None
    used_days: Optional[float] = None


class LeaveBalanceResponse(BaseModel):
    id: int
    user_id: int
    leave_type_id: int
    year: int
    allocated_days: float
    used_days: float
    remaining_days: float
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
