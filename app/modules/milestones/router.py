from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.common.responses import success_response, created_response

pm_only = require_roles("Project_Manager")
from app.modules.users.model import User
from app.modules.milestones.schema import MilestoneCreate, MilestoneUpdate, MilestoneResponse
from app.modules.milestones.service import MilestoneService

router = APIRouter()


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(pm_only)])
async def create_milestone(
    milestone_in: MilestoneCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    service = MilestoneService(db)
    milestone = await service.create_milestone(milestone_in, current_user)
    return created_response(data=milestone.model_dump(mode="json"), message="Milestone created successfully")


@router.get("/project/{project_id}", response_model=dict)
async def get_milestones_by_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    service = MilestoneService(db)
    milestones = await service.get_milestones_by_project(project_id)
    return success_response(data=[m.model_dump(mode="json") for m in milestones], message="Milestones retrieved successfully")


@router.get("/{milestone_id}", response_model=dict)
async def get_milestone(
    milestone_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    service = MilestoneService(db)
    milestone = await service.get_milestone(milestone_id)
    return success_response(data=milestone.model_dump(mode="json"), message="Milestone retrieved successfully")


@router.put("/{milestone_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def update_milestone(
    milestone_id: int,
    milestone_in: MilestoneUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    service = MilestoneService(db)
    milestone = await service.update_milestone(milestone_id, milestone_in, current_user)
    return success_response(data=milestone.model_dump(mode="json"), message="Milestone updated successfully")


@router.delete("/{milestone_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def delete_milestone(
    milestone_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    service = MilestoneService(db)
    await service.delete_milestone(milestone_id, current_user)
    return success_response(data=None, message="Milestone deleted successfully")
