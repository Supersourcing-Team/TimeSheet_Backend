from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.roles.schema import RoleResponse


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, max_length=50) # Auto-generated if not provided
    role_id: int = Field(..., ge=1)
    joining_date: Optional[date] = None
    ctc: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = "Pending"


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)
    role_id: Optional[int] = Field(None, ge=1)
    joining_date: Optional[date] = None
    ctc: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = None


class UserStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status ('Active' or 'Inactive')")


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    employee_id: str
    role_id: int
    joining_date: Optional[date] = None
    ctc: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime
    role: RoleResponse

    model_config = ConfigDict(from_attributes=True)
