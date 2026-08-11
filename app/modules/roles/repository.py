from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.role import Role


class RoleRepository:
    """Repository handling database queries for Roles."""

    @staticmethod
    async def list_roles(db: AsyncSession) -> List[Role]:
        result = await db.execute(select(Role).order_by(Role.id))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, role_id: int) -> Optional[Role]:
        result = await db.execute(select(Role).filter(Role.id == role_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Role]:
        result = await db.execute(select(Role).filter(Role.name == name))
        return result.scalar_one_or_none()
