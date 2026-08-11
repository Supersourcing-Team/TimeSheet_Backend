from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tool_allocation import ToolAllocation
from app.modules.tool_allocations.schema import ToolAllocationCreate, ToolAllocationUpdate


class ToolAllocationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, allocation_id: int) -> Optional[ToolAllocation]:
        result = await self.db.execute(
            select(ToolAllocation)
            .where(ToolAllocation.id == allocation_id, ToolAllocation.status == "Active")
        )
        return result.scalars().first()

    async def get_allocation(self, project_id: int, tool_id: int) -> Optional[ToolAllocation]:
        result = await self.db.execute(
            select(ToolAllocation)
            .where(
                and_(
                    ToolAllocation.project_id == project_id,
                    ToolAllocation.tool_id == tool_id,
                    ToolAllocation.status == "Active"
                )
            )
        )
        return result.scalars().first()

    async def get_by_project(self, project_id: int, skip: int = 0, limit: int = 100) -> List[ToolAllocation]:
        result = await self.db.execute(
            select(ToolAllocation)
            .where(ToolAllocation.project_id == project_id, ToolAllocation.status == "Active")
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_tool(self, tool_id: int, skip: int = 0, limit: int = 100) -> List[ToolAllocation]:
        result = await self.db.execute(
            select(ToolAllocation)
            .where(ToolAllocation.tool_id == tool_id, ToolAllocation.status == "Active")
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, allocation_in: ToolAllocationCreate) -> ToolAllocation:
        allocation = ToolAllocation(**allocation_in.model_dump())
        self.db.add(allocation)
        await self.db.commit()
        await self.db.refresh(allocation)
        return allocation

    async def update(self, allocation: ToolAllocation, allocation_in: ToolAllocationUpdate) -> ToolAllocation:
        update_data = allocation_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(allocation, field, value)
        await self.db.commit()
        await self.db.refresh(allocation)
        return allocation
