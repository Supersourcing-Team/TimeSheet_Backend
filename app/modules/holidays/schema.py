from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class HolidayBase(BaseModel):
    name: str
    date: date


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None


class HolidayResponse(HolidayBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
