from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.permissions import require_roles
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.modules.project_assignments.schema import ProjectAssignmentCreate, ProjectAssignmentResponse
from app.modules.project_assignments.service import ProjectAssignmentService

router = APIRouter()
pm_only = require_roles("Project_Manager")


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(pm_only)])
async def assign_user(assignment_in: ProjectAssignmentCreate, db: AsyncSession = Depends(get_db)):
    service = ProjectAssignmentService(db)
    assignment = await service.assign_user_to_project(assignment_in)
    return created_response(data=assignment.model_dump(mode="json"), message="User assigned to project successfully")


@router.get("/project/{project_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def get_project_assignments(project_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ProjectAssignmentService(db)
    assignments = await service.get_project_assignments(project_id, skip=skip, limit=limit)
    return success_response(data=[a.model_dump(mode="json") for a in assignments], message="Project assignments retrieved successfully")


@router.get("/user/me", response_model=dict)
async def get_my_assignments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns all active project assignments for the currently logged-in user."""
    service = ProjectAssignmentService(db)
    assignments = await service.get_user_assignments(current_user.id, skip=skip, limit=limit)
    return success_response(
        data=[a.model_dump(mode="json") for a in assignments],
        message="My project assignments retrieved successfully",
    )


@router.get("/user/{user_id}", response_model=dict)
async def get_user_assignments(
    user_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Rule: Employees can only see their own assignments. PMs can see any.
    if current_user.role.name != "Project_Manager" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own assignments")

    service = ProjectAssignmentService(db)
    assignments = await service.get_user_assignments(user_id, skip=skip, limit=limit)
    return success_response(data=[a.model_dump(mode="json") for a in assignments], message="User assignments retrieved successfully")


@router.delete("/{assignment_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def remove_assignment(assignment_id: int, db: AsyncSession = Depends(get_db)):
    service = ProjectAssignmentService(db)
    await service.remove_assignment(assignment_id)
    return success_response(message="Project assignment removed successfully")

