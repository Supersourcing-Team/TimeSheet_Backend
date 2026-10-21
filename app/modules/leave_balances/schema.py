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
    leave_type_name: Optional[str] = None
    year: int
    allocated_days: float
    used_days: float
    remaining_days: float
    updated_at: datetime
    # Authoritative Keka metadata & fields
    keka_leave_type_id: Optional[str] = None
    available_balance: Optional[float] = None
    annual_quota: Optional[float] = None
    accrued_days: Optional[float] = None
    source: str = "local"  # "keka" or "local"
    is_live: bool = False
    sync_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

