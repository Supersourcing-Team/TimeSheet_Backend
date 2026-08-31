from datetime import date, timedelta
from typing import List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException
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

    # -------------------------------------------------------------------------
    # Inline Mark-Leave validators
    # -------------------------------------------------------------------------

    @staticmethod
    async def validate_no_duplicate_leave(
        db: AsyncSession,
        user_id: int,
        leave_date: date,
    ) -> None:
        """Raise ConflictException if an Approved/Pending leave already exists for this date."""
        from app.modules.leave_requests.repository import LeaveRequestRepository
        existing = await LeaveRequestRepository.get_approved_leaves_for_date(db, user_id, leave_date)
        if existing:
            raise ConflictException(
                detail=f"You already have a leave record for {leave_date}. "
                       "Cancel it first before marking a new one."
            )

    @staticmethod
    async def validate_no_timesheet_conflict(
        db: AsyncSession,
        user_id: int,
        leave_date: date,
        leave_duration_type: str,
        partial_start_time: Optional[str] = None,
        partial_end_time: Optional[str] = None,
    ) -> None:
        """Raise BadRequestException if existing timesheet hours conflict with the requested leave."""
        from app.modules.timesheets.repository import TimesheetRepository

        total_hours = await TimesheetRepository.get_daily_total_hours(db, user_id, leave_date)
        if total_hours <= 0:
            return  # No timesheet entries → no conflict

        if leave_duration_type == "full_day":
            raise BadRequestException(
                detail=f"You have {total_hours}h logged on {leave_date}. "
                       "Delete or update those timesheet entries before marking a full-day leave."
            )

        if leave_duration_type == "half_day":
            # Allow up to 4h of timesheet on a half-day leave
            if total_hours > 4.0:
                raise BadRequestException(
                    detail=f"You already have {total_hours}h logged on {leave_date}, "
                           "which exceeds the 4h limit for a half-day leave."
                )

        if leave_duration_type == "partial_day" and partial_start_time and partial_end_time:
            start_h, start_m = map(int, partial_start_time.split(":"))
            end_h, end_m = map(int, partial_end_time.split(":"))
            leave_hours = (end_h * 60 + end_m - start_h * 60 - start_m) / 60.0
            available = 8.0 - leave_hours
            if total_hours > available:
                raise BadRequestException(
                    detail=f"You have {total_hours}h logged on {leave_date}. "
                           f"With a partial leave from {partial_start_time} to {partial_end_time} "
                           f"({leave_hours:.1f}h), only {available:.1f}h can be logged."
                )

    @staticmethod
    def validate_partial_time(
        partial_start_time: Optional[str],
        partial_end_time: Optional[str],
    ) -> None:
        """Validate partial leave time window: start < end and max 2 hours."""
        if not partial_start_time or not partial_end_time:
            raise BadRequestException(detail="partial_start_time and partial_end_time are required for partial_day leave.")

        try:
            start_h, start_m = map(int, partial_start_time.split(":"))
            end_h, end_m = map(int, partial_end_time.split(":"))
        except ValueError:
            raise BadRequestException(detail="Times must be in HH:MM format (e.g. '09:00').")

        start_mins = start_h * 60 + start_m
        end_mins = end_h * 60 + end_m

        if end_mins <= start_mins:
            raise BadRequestException(detail="Partial leave end time must be after start time.")

        duration_hours = (end_mins - start_mins) / 60.0
        if duration_hours > 2.0:
            raise BadRequestException(
                detail=f"Maximum partial leave duration is 2 hours. "
                       f"Selected duration is {duration_hours:.1f} hours."
            )
        if duration_hours <= 0:
            raise BadRequestException(detail="Partial leave duration must be greater than 0.")

