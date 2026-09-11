from datetime import date as dt_date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class HolidayBase(BaseModel):
    name: str
    date: dt_date
    type: str = Field(default="National")
    description: Optional[str] = None
    is_mandatory: bool = Field(default=True)


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[dt_date] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_mandatory: Optional[bool] = None


class HolidayResponse(HolidayBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
