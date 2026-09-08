from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.permissions import require_roles
from app.modules.tool_allocations.schema import ToolAllocationCreate, ToolAllocationUpdate
from app.modules.tool_allocations.service import ToolAllocationService

router = APIRouter()
pm_only = require_roles("Project_Manager")
pm_and_am = require_roles(["Project_Manager", "Account_Manager"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(pm_only)])
async def allocate_tool(allocation_in: ToolAllocationCreate, db: AsyncSession = Depends(get_db)):
    service = ToolAllocationService(db)
    allocation = await service.allocate_tool(allocation_in)
    return created_response(data=allocation.model_dump(mode="json"), message="Tool allocated successfully")


@router.get("/project/{project_id}", response_model=dict, dependencies=[Depends(pm_and_am)])
async def get_project_allocations(project_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ToolAllocationService(db)
    allocations = await service.get_project_allocations(project_id, skip=skip, limit=limit)
    return success_response(data=[a.model_dump(mode="json") for a in allocations], message="Project tool allocations retrieved successfully")


@router.get("/tool/{tool_id}", response_model=dict, dependencies=[Depends(pm_and_am)])
async def get_tool_allocations(tool_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ToolAllocationService(db)
    allocations = await service.get_tool_allocations(tool_id, skip=skip, limit=limit)
    return success_response(data=[a.model_dump(mode="json") for a in allocations], message="Tool allocations retrieved successfully")


@router.put("/{allocation_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def update_tool_allocation(allocation_id: int, allocation_in: ToolAllocationUpdate, db: AsyncSession = Depends(get_db)):
    service = ToolAllocationService(db)
    allocation = await service.update_tool_allocation(allocation_id, allocation_in)
    return success_response(data=allocation.model_dump(mode="json"), message="Tool allocation updated successfully")


@router.put("/{allocation_id}/deallocate", response_model=dict, dependencies=[Depends(pm_only)])
async def deallocate_tool(allocation_id: int, db: AsyncSession = Depends(get_db)):
    service = ToolAllocationService(db)
    allocation = await service.deallocate_tool(allocation_id)
    return success_response(data=allocation.model_dump(mode="json"), message="Tool deallocated successfully")
