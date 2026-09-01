from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MilestoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    start_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    budget: Optional[float] = None
    status: str = Field(default="planned", max_length=20)
    weight_percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class MilestoneCreate(MilestoneBase):
    project_id: int = Field(..., ge=1)


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    start_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    budget: Optional[float] = None
    status: Optional[str] = Field(None, max_length=20)
    weight_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)


class MilestoneResponse(MilestoneBase):
    id: int
    project_id: int
    actual_achievement_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
