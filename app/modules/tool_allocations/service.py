from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from datetime import date

from app.modules.tool_allocations.repository import ToolAllocationRepository
from app.modules.tool_allocations.schema import ToolAllocationCreate, ToolAllocationUpdate, ToolAllocationResponse
from app.modules.projects.repository import ProjectRepository
from app.modules.tools.repository import ToolRepository


class ToolAllocationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ToolAllocationRepository(db)
        self.project_repo = ProjectRepository(db)
        self.tool_repo = ToolRepository(db)

    async def allocate_tool(self, allocation_in: ToolAllocationCreate) -> ToolAllocationResponse:
        # Check if project exists and is active
        project = await self.project_repo.get_by_id(allocation_in.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Check if tool exists and is active
        tool = await self.tool_repo.get_by_id(allocation_in.tool_id)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found or is inactive")

        # Check if already assigned
        existing_allocation = await self.repository.get_allocation(allocation_in.project_id, allocation_in.tool_id)
        if existing_allocation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool is already allocated to this project")

        allocation = await self.repository.create(allocation_in)
        return ToolAllocationResponse.model_validate(allocation)

    async def get_project_allocations(self, project_id: int, skip: int = 0, limit: int = 100) -> List[ToolAllocationResponse]:
        # Check if project exists
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            
        allocations = await self.repository.get_by_project(project_id, skip=skip, limit=limit)
        return [ToolAllocationResponse.model_validate(a) for a in allocations]

    async def get_tool_allocations(self, tool_id: int, skip: int = 0, limit: int = 100) -> List[ToolAllocationResponse]:
        # Check if tool exists
        tool = await self.tool_repo.get_by_id(tool_id)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
            
        allocations = await self.repository.get_by_tool(tool_id, skip=skip, limit=limit)
        return [ToolAllocationResponse.model_validate(a) for a in allocations]

    async def update_tool_allocation(self, allocation_id: int, allocation_in: ToolAllocationUpdate) -> ToolAllocationResponse:
        allocation = await self.repository.get_by_id(allocation_id)
        if not allocation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool allocation not found")

        updated_allocation = await self.repository.update(allocation, allocation_in)
        return ToolAllocationResponse.model_validate(updated_allocation)

    async def deallocate_tool(self, allocation_id: int) -> ToolAllocationResponse:
        allocation = await self.repository.get_by_id(allocation_id)
        if not allocation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool allocation not found")
        
        # Soft delete by setting status and deallocation date
        update_data = ToolAllocationUpdate(
            deallocation_date=date.today(),
            status="Inactive"
        )
        updated_allocation = await self.repository.update(allocation, update_data)
        return ToolAllocationResponse.model_validate(updated_allocation)
