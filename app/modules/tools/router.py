from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.permissions import require_roles
from app.modules.tools.schema import ToolCreate, ToolUpdate
from app.modules.tools.service import ToolService

router = APIRouter()
admin_only = require_roles("Admin")
view_tools_roles = require_roles("Admin", "Project_Manager", "Account_Manager")


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(admin_only)])
async def create_tool(tool_in: ToolCreate, db: AsyncSession = Depends(get_db)):
    service = ToolService(db)
    tool = await service.create_tool(tool_in)
    return created_response(data=tool.model_dump(mode="json"), message="Tool created successfully")


@router.get("", response_model=dict, dependencies=[Depends(view_tools_roles)])
async def get_tools(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ToolService(db)
    tools = await service.get_all_tools(skip=skip, limit=limit)
    return success_response(data=[t.model_dump(mode="json") for t in tools], message="Tools retrieved successfully")


@router.get("/{tool_id}", response_model=dict, dependencies=[Depends(view_tools_roles)])
async def get_tool(tool_id: int, db: AsyncSession = Depends(get_db)):
    service = ToolService(db)
    tool = await service.get_tool(tool_id)
    return success_response(data=tool.model_dump(mode="json"), message="Tool retrieved successfully")


@router.put("/{tool_id}", response_model=dict, dependencies=[Depends(admin_only)])
async def update_tool(tool_id: int, tool_in: ToolUpdate, db: AsyncSession = Depends(get_db)):
    service = ToolService(db)
    tool = await service.update_tool(tool_id, tool_in)
    return success_response(data=tool.model_dump(mode="json"), message="Tool updated successfully")


@router.delete("/{tool_id}", response_model=dict, dependencies=[Depends(admin_only)])
async def delete_tool(tool_id: int, db: AsyncSession = Depends(get_db)):
    service = ToolService(db)
    await service.delete_tool(tool_id)
    return success_response(message="Tool deleted successfully")

