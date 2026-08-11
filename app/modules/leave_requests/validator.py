from datetime import date, timedelta
from typing import List, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.holidays.repository import HolidayRepository


class LeaveRequestValidator:
    """Validates date ranges, calculates working days (excluding weekends & holidays), and checks leave balances."""

    @staticmethod
    async def get_holiday_dates(db: AsyncSession, start_date: date, end_date: date) -> Set[date]:
        holidays = await HolidayRepository.get_all(db)
        holiday_dates = {h.date for h in holidays if start_date <= h.date <= end_date}
        return holiday_dates


    @staticmethod
    async def calculate_working_days(db: AsyncSession, start_date: date, end_date: date) -> int:
        if start_date > end_date:
            raise BadRequestException(detail="start_date must be less than or equal to end_date")

        holiday_dates = await LeaveRequestValidator.get_holiday_dates(db, start_date, end_date)
        
        working_days = 0
        current = start_date
        while current <= end_date:
            # 5 is Saturday, 6 is Sunday
            if current.weekday() not in (5, 6) and current not in holiday_dates:
                working_days += 1
            current += timedelta(days=1)

        return working_days
