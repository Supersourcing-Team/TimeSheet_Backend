from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules.milestones.schema import MilestoneResponse


class ProjectCreate(BaseModel):
    client_id: int = Field(..., ge=1)
    project_manager_id: int = Field(..., ge=1)
    project_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
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
    budget: Optional[float] = Field(None, ge=0)
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
    client_name: Optional[str] = None
    project_manager_name: Optional[str] = None
    assigned_user_ids: list[int] = Field(default_factory=list)
    tools: list[dict] = Field(default_factory=list)
    logged_hours: float = 0.0
    cost: float = 0.0
    revenue: float = 0.0
    profit: float = 0.0
    milestones: list[MilestoneResponse] = Field(default_factory=list)
    completion_percentage: float = 0.0

    model_config = ConfigDict(from_attributes=True)
