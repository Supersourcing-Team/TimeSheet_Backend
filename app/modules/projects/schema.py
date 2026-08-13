from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    client_id: int = Field(..., ge=1)
    project_manager_id: int = Field(..., ge=1)
    project_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode='after')
    def validate_dates(self) -> 'ProjectCreate':
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class ProjectUpdate(BaseModel):
    client_id: Optional[int] = Field(None, ge=1)
    project_manager_id: Optional[int] = Field(None, ge=1)
    project_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=20)

    @model_validator(mode='after')
    def validate_dates(self) -> 'ProjectUpdate':
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class ProjectResponse(BaseModel):
    id: int
    client_id: int
    project_manager_id: int
    project_name: str
    description: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProjectDetailResponse(ProjectResponse):
    client_name: Optional[str] = None
    project_manager_name: Optional[str] = None
    assigned_user_ids: list[int] = []
    tools: list[dict] = []
