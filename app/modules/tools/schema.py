from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    cost_per_month: float = Field(default=0.0, ge=0.0)


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    cost_per_month: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = Field(None, max_length=20)


class ToolResponse(BaseModel):
    id: int
    name: str
    category: str
    cost_per_month: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
