from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)


class ClientResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
