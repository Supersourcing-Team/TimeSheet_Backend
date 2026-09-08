from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.modules.users.model import User


class UserRepository:
    """Repository handling database operations for Users."""

    @staticmethod
    async def create(db: AsyncSession, user: User) -> User:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # Fetch with role relationship loaded
        return await UserRepository.get_by_id(db, user.id)

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.role), selectinload(User.department))
            .filter(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.role), selectinload(User.department))
            .filter(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_employee_id(db: AsyncSession, employee_id: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.role), selectinload(User.department))
            .filter(User.employee_id == employee_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        role_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[User], int]:
        query = select(User).options(selectinload(User.role), selectinload(User.department))
        count_query = select(func.count(User.id))

        if role_id is not None:
            query = query.filter(User.role_id == role_id)
            count_query = count_query.filter(User.role_id == role_id)

        if status:
            query = query.filter(User.status == status)
            count_query = count_query.filter(User.status == status)

        if search:
            search_pattern = f"%{search}%"
            search_filter = or_(
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.employee_id.ilike(search_pattern),
            )
            query = query.filter(search_filter)
            count_query = count_query.filter(search_filter)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(User.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        users = list(result.scalars().all())

        return users, total

    @staticmethod
    async def update(db: AsyncSession, user: User, update_data: dict) -> User:
        for field, value in update_data.items():
            if value is not None:
                setattr(user, field, value)
        await db.commit()
        await db.refresh(user)
        return await UserRepository.get_by_id(db, user.id)

    @staticmethod
    async def toggle_status(db: AsyncSession, user: User, new_status: str) -> User:
        user.status = new_status
        await db.commit()
        await db.refresh(user)
        return await UserRepository.get_by_id(db, user.id)
