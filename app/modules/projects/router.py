from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.permissions import require_roles
from app.modules.projects.schema import ProjectCreate, ProjectUpdate, ProjectResponse
from app.modules.projects.service import ProjectService


router = APIRouter()
pm_only = require_roles("Project_Manager")


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(pm_only)])
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    service = ProjectService(db)
    project = await service.create_project(project_in)
    return success_response(data=project.model_dump(mode="json"), message="Project created successfully")


@router.get("/", response_model=dict, dependencies=[Depends(pm_only)])
async def get_projects(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ProjectService(db)
    projects = await service.get_all_projects(skip=skip, limit=limit)
    return success_response(data=[p.model_dump(mode="json") for p in projects], message="Projects retrieved successfully")


@router.get("/{project_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    return success_response(data=project.model_dump(mode="json"), message="Project retrieved successfully")


@router.put("/{project_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def update_project(project_id: int, project_in: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    service = ProjectService(db)
    project = await service.update_project(project_id, project_in)
    return success_response(data=project.model_dump(mode="json"), message="Project updated successfully")



@router.delete("/{project_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    service = ProjectService(db)
    await service.delete_project(project_id)
    return success_response(message="Project deleted successfully")
