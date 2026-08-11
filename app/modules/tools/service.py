from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.modules.tools.repository import ToolRepository
from app.modules.tools.schema import ToolCreate, ToolUpdate, ToolResponse


class ToolService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ToolRepository(db)

    async def create_tool(self, tool_in: ToolCreate) -> ToolResponse:
        existing_tool = await self.repository.get_by_name(tool_in.name)
        if existing_tool:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool with this name already exists")
        
        tool = await self.repository.create(tool_in)
        return ToolResponse.model_validate(tool)

    async def get_tool(self, tool_id: int) -> ToolResponse:
        tool = await self.repository.get_by_id(tool_id)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
        return ToolResponse.model_validate(tool)

    async def get_all_tools(self, skip: int = 0, limit: int = 100) -> List[ToolResponse]:
        tools = await self.repository.get_all(skip=skip, limit=limit)
        return [ToolResponse.model_validate(t) for t in tools]

    async def update_tool(self, tool_id: int, tool_in: ToolUpdate) -> ToolResponse:
        tool = await self.repository.get_by_id(tool_id)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
        
        if tool_in.name and tool_in.name != tool.name:
            existing = await self.repository.get_by_name(tool_in.name)
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool with this name already exists")

        updated_tool = await self.repository.update(tool, tool_in)
        return ToolResponse.model_validate(updated_tool)

    async def delete_tool(self, tool_id: int) -> None:
        tool = await self.repository.get_by_id(tool_id)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
        
        await self.repository.soft_delete(tool)
