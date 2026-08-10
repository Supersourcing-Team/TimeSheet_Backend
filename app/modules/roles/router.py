from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.modules.roles.schema import RoleResponse
from app.modules.roles.service import RoleService

router = APIRouter()


@router.get("", summary="List all system roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns a list of all system roles (Admin, Project_Manager, Account_Manager, Employee).
    """
    roles = await RoleService.get_all_roles(db)
    roles_data = [RoleResponse.model_validate(role).model_dump(mode='json') for role in roles]
    return success_response(
        data=roles_data,
        message="Roles retrieved successfully",
    )
