from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict

class WorkingCalendarBase(BaseModel):
    full_day_hours: float
    half_day_hours: float
    partial_day_min_hours: float
    partial_day_max_hours: float
    working_days: Dict[str, bool]
    time_zone: str

class WorkingCalendarCreate(WorkingCalendarBase):
    pass

class WorkingCalendarUpdate(BaseModel):
    full_day_hours: Optional[float] = None
    half_day_hours: Optional[float] = None
    partial_day_min_hours: Optional[float] = None
    partial_day_max_hours: Optional[float] = None
    working_days: Optional[Dict[str, bool]] = None
    time_zone: Optional[str] = None

class WorkingCalendarResponse(WorkingCalendarBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
