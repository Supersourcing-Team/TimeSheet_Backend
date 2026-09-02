from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.roles.model import Role
from app.modules.roles.repository import RoleRepository


class RoleService:
    """Service layer handling business logic for Roles."""

    @staticmethod
    async def get_all_roles(db: AsyncSession) -> List[Role]:
        return await RoleRepository.list_roles(db)

    @staticmethod
    async def get_role_by_id(db: AsyncSession, role_id: int) -> Role:
        role = await RoleRepository.get_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with ID {role_id} not found.",
            )
        return role
