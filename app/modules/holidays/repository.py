from datetime import date
from typing import List, Optional
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import Holiday


class HolidayRepository:
    @staticmethod
    async def get_all(
        db: AsyncSession, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Holiday]:
        query = select(Holiday)
        if year:
            query = query.where(extract("year", Holiday.date) == year)
        if month:
            query = query.where(extract("month", Holiday.date) == month)
        query = query.order_by(Holiday.date.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, holiday_id: int) -> Optional[Holiday]:
        query = select(Holiday).where(Holiday.id == holiday_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_date(db: AsyncSession, holiday_date: date) -> Optional[Holiday]:
        query = select(Holiday).where(Holiday.date == holiday_date)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, **data) -> Holiday:
        holiday = Holiday(**data)
        db.add(holiday)
        await db.commit()
        await db.refresh(holiday)
        return holiday

    @staticmethod
    async def update(db: AsyncSession, holiday: Holiday, **data) -> Holiday:
        for key, value in data.items():
            if value is not None:
                setattr(holiday, key, value)
        await db.commit()
        await db.refresh(holiday)
        return holiday

    @staticmethod
    async def delete(db: AsyncSession, holiday: Holiday) -> None:
        await db.delete(holiday)
        await db.commit()
