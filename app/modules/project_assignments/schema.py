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


class BatchProjectAssignmentCreate(BaseModel):
    project_ids: list[int] = Field(..., min_length=1, description="List of project IDs")
    user_ids: list[int] = Field(..., min_length=1, description="List of user IDs")


class BatchProjectAssignmentResponse(BaseModel):
    assigned_count: int
    reactivated_count: int
    skipped_count: int
    total_requested: int
    message: str

