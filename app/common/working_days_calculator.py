"""
Working Days Calculator — Shared utility for the Employee Utilization module.

Computes working days, available hours, and hourly cost using:
- WorkingCalendar config (which weekdays are working days, full_day_hours)
- Holiday table (company holidays to exclude)
- Employee CTC (for hourly cost derivation)

All financial calculations across the system should use these functions
instead of hardcoded values (260, 22, 8, 30.44, etc.).
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.holidays.model import Holiday
from app.modules.working_calendar.model import WorkingCalendar


# Day-of-week index mapping (Python: Monday=0 ... Sunday=6)
_WEEKDAY_KEYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
]


async def _get_working_calendar(db: AsyncSession) -> WorkingCalendar:
    """Fetch the company's working calendar config, or return sensible defaults."""
    result = await db.execute(select(WorkingCalendar).limit(1))
    config = result.scalars().first()
    if config:
        return config

    # Fallback defaults if no config row exists
    class _Defaults:
        full_day_hours = 8.0
        half_day_hours = 4.0
        working_days = {
            "monday": True, "tuesday": True, "wednesday": True,
            "thursday": True, "friday": True, "saturday": False, "sunday": False,
        }
    return _Defaults()


async def _get_holidays_in_range(db: AsyncSession, start: date, end: date) -> set:
    """Return a set of holiday dates between start and end (inclusive)."""
    query = (
        select(Holiday.date)
        .where(Holiday.date >= start, Holiday.date <= end)
    )
    result = await db.execute(query)
    return {row[0] for row in result.all()}


def _is_working_day(d: date, working_days_config: dict) -> bool:
    """Check if a given date is a configured working day (by weekday name)."""
    weekday_key = _WEEKDAY_KEYS[d.weekday()]
    return bool(working_days_config.get(weekday_key, False))


async def get_working_days(
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> int:
    """
    Count working days between start_date and end_date (inclusive).

    Excludes:
    - Non-working weekdays (per WorkingCalendar config)
    - Company holidays (per Holiday table)
    """
    if not start_date or not end_date or end_date < start_date:
        return 0

    calendar = await _get_working_calendar(db)
    working_days_config = calendar.working_days or {}
    holidays = await _get_holidays_in_range(db, start_date, end_date)

    count = 0
    current = start_date
    while current <= end_date:
        if _is_working_day(current, working_days_config) and current not in holidays:
            count += 1
        current += timedelta(days=1)

    return count


async def get_available_hours(
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> float:
    """
    Available Hours = Working Days × Full Day Hours

    Uses company WorkingCalendar config for hours/day.
    """
    if not start_date or not end_date:
        return 0.0

    calendar = await _get_working_calendar(db)
    days = await get_working_days(start_date, end_date, db)
    hours_per_day = calendar.full_day_hours or 8.0
    return float(days * hours_per_day)


async def get_working_days_in_month(
    year: int,
    month: int,
    db: AsyncSession,
) -> int:
    """Count working days in a given calendar month."""
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    return await get_working_days(first_day, last_day, db)


async def get_hourly_cost(
    annual_ctc: float,
    db: AsyncSession,
) -> float:
    """
    Hourly Cost = Annual CTC / 12 / Working Days per Month / Hours per Day

    Working days per month is derived from the WorkingCalendar config
    by counting how many weekdays are marked as working (e.g. Mon-Fri = 5)
    and multiplying by ~4.33 weeks/month.
    """
    if not annual_ctc or annual_ctc <= 0:
        return 0.0

    calendar = await _get_working_calendar(db)
    working_days_config = calendar.working_days or {}
    hours_per_day = calendar.full_day_hours or 8.0

    # Count configured working days per week
    working_days_per_week = sum(1 for day in _WEEKDAY_KEYS if working_days_config.get(day, False))
    if working_days_per_week == 0:
        return 0.0

    # Average working days per month ≈ working_days_per_week × 52 / 12
    working_days_per_month = (working_days_per_week * 52) / 12  # e.g. 5 × 52/12 ≈ 21.67

    monthly_cost = annual_ctc / 12.0
    daily_cost = monthly_cost / working_days_per_month
    hourly_cost = daily_cost / hours_per_day

    return round(hourly_cost, 2)


async def get_daily_cost(
    annual_ctc: float,
    db: AsyncSession,
) -> float:
    """
    Daily Cost = Annual CTC / 12 / Working Days per Month
    """
    if not annual_ctc or annual_ctc <= 0:
        return 0.0

    calendar = await _get_working_calendar(db)
    working_days_config = calendar.working_days or {}

    working_days_per_week = sum(1 for day in _WEEKDAY_KEYS if working_days_config.get(day, False))
    if working_days_per_week == 0:
        return 0.0

    working_days_per_month = (working_days_per_week * 52) / 12

    return round((annual_ctc / 12.0) / working_days_per_month, 2)
