from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.project_assignment import ProjectAssignment
from app.modules.timesheets.repository import TimesheetRepository


class TimesheetValidator:
    """Validates timesheet hour limits (max 8h/day) and project assignment ownership."""

    @staticmethod
    async def validate_project_assignment(
        db: AsyncSession,
        user_id: int,
        project_assignment_id: int,
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

        if getattr(assignment, "assignment_status", "Active") != "Active":
            raise BadRequestException(
                detail="Project assignment is not active."
            )

        return assignment

    @staticmethod
    async def validate_daily_hours(
        db: AsyncSession,
        user_id: int,
        timesheet_date: date,
        new_hours: float,
        exclude_id: Optional[int] = None,
    ) -> None:
        if new_hours <= 0:
            raise BadRequestException(detail="Logged hours must be greater than 0.")
        if new_hours > 8.0:
            raise BadRequestException(detail="Single entry cannot exceed 8.0 hours.")

        existing_total = await TimesheetRepository.get_daily_total_hours(
            db, user_id, timesheet_date, exclude_id=exclude_id
        )

        total_after_add = existing_total + new_hours
        if total_after_add > 8.0:
            raise BadRequestException(
                detail=f"Exceeds daily 8-hour max limit. Logged: {existing_total}h, Trying to add: {new_hours}h (Total: {total_after_add}h)."
            )
