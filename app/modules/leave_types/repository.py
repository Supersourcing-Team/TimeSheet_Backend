from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_type import LeaveType


class LeaveTypeRepository:
    @staticmethod
    async def get_all(db: AsyncSession, active_only: bool = True) -> List[LeaveType]:
        query = select(LeaveType)
        if active_only:
            query = query.where(LeaveType.is_active.is_(True))
        query = query.order_by(LeaveType.id.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, leave_type_id: int) -> Optional[LeaveType]:
        query = select(LeaveType).where(LeaveType.id == leave_type_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[LeaveType]:
        query = select(LeaveType).where(LeaveType.name == name)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[LeaveType]:
        query = select(LeaveType).where(LeaveType.code == code)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, **data) -> LeaveType:
        leave_type = LeaveType(**data)
        db.add(leave_type)
        await db.commit()
        await db.refresh(leave_type)
        return leave_type

    @staticmethod
    async def update(db: AsyncSession, leave_type: LeaveType, **data) -> LeaveType:
        for key, value in data.items():
            if value is not None:
                setattr(leave_type, key, value)
        await db.commit()
        await db.refresh(leave_type)
        return leave_type

    @staticmethod
    async def delete(db: AsyncSession, leave_type: LeaveType) -> LeaveType:
        leave_type.is_active = False
        await db.commit()
        await db.refresh(leave_type)
        return leave_type
