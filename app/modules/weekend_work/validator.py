from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.project_assignment import ProjectAssignment
from app.modules.holidays.repository import HolidayRepository


class WeekendWorkValidator:
    """Validates date requirements (Saturday, Sunday, or Holiday) and project assignment ownership."""

    @staticmethod
    async def validate_weekend_or_holiday_date(db: AsyncSession, work_date: date) -> None:
        # 5 is Saturday, 6 is Sunday
        if work_date.weekday() in (5, 6):
            return

        # Check if work_date is a company public holiday
        holiday = await HolidayRepository.get_by_date(db, work_date)
        if not holiday:
            raise BadRequestException(
                detail="Weekend work requests are only permitted on Saturdays, Sundays, or official public holidays."
            )

    @staticmethod
    async def validate_project_assignment(
        db: AsyncSession, user_id: int, project_assignment_id: int
    ) -> ProjectAssignment:
        result = await db.execute(
            select(ProjectAssignment).filter(
                ProjectAssignment.id == project_assignment_id,
                ProjectAssignment.user_id == user_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise BadRequestException(
                detail="Invalid project assignment. Assignment does not exist or belong to you."
            )
        return assignment
