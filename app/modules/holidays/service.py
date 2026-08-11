from datetime import date
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import Holiday
from app.modules.holidays.repository import HolidayRepository
from app.modules.holidays.schema import HolidayCreate, HolidayUpdate


class HolidayService:
    @staticmethod
    async def get_holidays(
        db: AsyncSession, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Holiday]:
        return await HolidayRepository.get_all(db, year, month)

    @staticmethod
    async def get_holiday(db: AsyncSession, holiday_id: int) -> Holiday:
        holiday = await HolidayRepository.get_by_id(db, holiday_id)
        if not holiday:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Holiday with ID {holiday_id} not found",
            )
        return holiday

    @staticmethod
    async def create_holiday(db: AsyncSession, data: HolidayCreate) -> Holiday:
        existing = await HolidayRepository.get_by_date(db, data.date)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Holiday already exists for date {data.date}",
            )
        return await HolidayRepository.create(db, name=data.name, holiday_date=data.date)

    @staticmethod
    async def update_holiday(db: AsyncSession, holiday_id: int, data: HolidayUpdate) -> Holiday:
        holiday = await HolidayService.get_holiday(db, holiday_id)
        if data.date and data.date != holiday.date:
            existing = await HolidayRepository.get_by_date(db, data.date)
            if existing and existing.id != holiday_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Holiday already exists for date {data.date}",
                )
        return await HolidayRepository.update(db, holiday, **data.model_dump(exclude_unset=True))

    @staticmethod
    async def delete_holiday(db: AsyncSession, holiday_id: int) -> None:
        holiday = await HolidayService.get_holiday(db, holiday_id)
        await HolidayRepository.delete(db, holiday)
