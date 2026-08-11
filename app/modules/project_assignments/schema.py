from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProjectAssignmentCreate(BaseModel):
    project_id: int = Field(..., ge=1, description="ID of the project")
    user_id: int = Field(..., ge=1, description="ID of the user to assign")


class ProjectAssignmentResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
