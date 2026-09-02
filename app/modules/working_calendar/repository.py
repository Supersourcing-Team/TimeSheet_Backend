from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.modules.working_calendar.model import WorkingCalendar

class WorkingCalendarRepository:
    @staticmethod
    async def get_config(db: AsyncSession) -> Optional[WorkingCalendar]:
        result = await db.execute(select(WorkingCalendar).limit(1))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, **kwargs) -> WorkingCalendar:
        obj = WorkingCalendar(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    @staticmethod
    async def update(db: AsyncSession, obj: WorkingCalendar, **kwargs) -> WorkingCalendar:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await db.commit()
        await db.refresh(obj)
        return obj
