from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=255)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    id: int
    is_active: bool
    employee_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
