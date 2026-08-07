from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User


class AuthRepository:
    """Repository handling database queries for Authentication."""

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User).options(selectinload(User.role)).filter(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(
            select(User).options(selectinload(User.role)).filter(User.id == user_id)
        )
        return result.scalar_one_or_none()
