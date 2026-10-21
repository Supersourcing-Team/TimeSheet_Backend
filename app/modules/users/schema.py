from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.roles.schema import RoleResponse
from app.modules.departments.schema import DepartmentResponse


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, max_length=50) # Auto-generated if not provided
    role_id: int = Field(..., ge=1)
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    ctc: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = "Pending"
    middle_name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=150)
    mobile_number: Optional[str] = Field(None, max_length=25)
    job_title: Optional[str] = Field(None, max_length=150)
    secondary_job_title: Optional[str] = Field(None, max_length=150)
    business_unit: Optional[str] = Field(None, max_length=150)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=150)
    legal_entity: Optional[str] = Field(None, max_length=150)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)
    role_id: Optional[int] = Field(None, ge=1)
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    ctc: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = None
    middle_name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=150)
    mobile_number: Optional[str] = Field(None, max_length=25)
    job_title: Optional[str] = Field(None, max_length=150)
    secondary_job_title: Optional[str] = Field(None, max_length=150)
    business_unit: Optional[str] = Field(None, max_length=150)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=150)
    legal_entity: Optional[str] = Field(None, max_length=150)


class UserStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status ('Active' or 'Inactive')")


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    employee_id: str
    role_id: int
    department_id: Optional[int] = None
    joining_date: Optional[date] = None
    ctc: Optional[float] = None
    status: str
    middle_name: Optional[str] = None
    display_name: Optional[str] = None
    mobile_number: Optional[str] = None
    job_title: Optional[str] = None
    secondary_job_title: Optional[str] = None
    business_unit: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    location: Optional[str] = None
    legal_entity: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    role: RoleResponse
    department: Optional[DepartmentResponse] = None
    is_keka_synced: bool = False
    keka_employee_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

