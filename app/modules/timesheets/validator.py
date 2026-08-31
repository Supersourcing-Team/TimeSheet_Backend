from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.modules.timesheets.repository import TimesheetRepository


class TimesheetValidator:
    """Validates timesheet date rules, hour limits (max 24h/day), and project assignment ownership."""

    @staticmethod
    def validate_not_future_date(timesheet_date: date) -> None:
        if timesheet_date > date.today():
            raise BadRequestException(detail="Cannot log timesheets for future dates.")

    @staticmethod
    async def validate_project_assignment(
        db: AsyncSession,
        user_id: int,
        project_assignment_id: int,
    ) -> ProjectAssignment:
        result = await db.execute(
            select(ProjectAssignment)
            .options(selectinload(ProjectAssignment.project).selectinload(Project.assignments))
            .filter(ProjectAssignment.id == project_assignment_id)
        )
        assignment = result.scalar_one_or_none()
        if not assignment or assignment.user_id != user_id:
            raise ForbiddenException(detail="User is not assigned to this project.")

        project = assignment.project
        if not project or user_id not in project.assigned_user_ids:
            raise ForbiddenException(detail="User is not assigned to this project.")

        if getattr(assignment, "assignment_status", "Active") != "Active" or not assignment.is_active:
            raise ForbiddenException(detail="Project assignment is not active.")

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
        if new_hours > 24.0:
            raise BadRequestException(detail="Single entry cannot exceed 24.0 hours.")

        existing_total = await TimesheetRepository.get_daily_total_hours(
            db, user_id, timesheet_date, exclude_id=exclude_id
        )

        total_after_add = existing_total + new_hours
        if total_after_add > 24.0:
            raise BadRequestException(
                detail=f"Exceeds daily 24-hour max limit. Logged: {existing_total}h, Trying to add: {new_hours}h (Total: {total_after_add}h)."
            )

    @staticmethod
    async def validate_no_leave_conflict(
        db: AsyncSession,
        user_id: int,
        timesheet_date: date,
        new_hours: float,
    ) -> None:
        """
        Check if an approved leave exists for this date and validate that the
        timesheet hours don't violate the leave restriction.
        Raises BadRequestException if:
        - Full-day leave → no hours allowed
        - Half-day leave → max 4 hours allowed
        - Partial-day leave → max (8 - leave_hours) hours allowed
        """
        from app.modules.leave_requests.repository import LeaveRequestRepository

        leaves = await LeaveRequestRepository.get_approved_leaves_for_date(db, user_id, timesheet_date)
        if not leaves:
            return  # No leave → allow timesheet

        leave = leaves[0]
        duration = leave.leave_duration_type or "full_day"

        if duration == "full_day":
            raise BadRequestException(
                detail=f"You are on full-day leave on {timesheet_date}. "
                       "Timesheet entry is not allowed for this date."
            )

        if duration == "half_day":
            max_hours = 4.0
            existing_total = await TimesheetRepository.get_daily_total_hours(db, user_id, timesheet_date)
            if existing_total + new_hours > max_hours:
                raise BadRequestException(
                    detail=f"You are on half-day leave on {timesheet_date}. "
                           f"Maximum allowed hours: {max_hours}h. "
                           f"You have already logged {existing_total}h and are trying to add {new_hours}h."
                )

        if duration == "partial_day" and leave.partial_start_time and leave.partial_end_time:
            start_h, start_m = map(int, leave.partial_start_time.split(":"))
            end_h, end_m = map(int, leave.partial_end_time.split(":"))
            leave_hours = (end_h * 60 + end_m - start_h * 60 - start_m) / 60.0
            max_hours = max(0.0, 8.0 - leave_hours)
            existing_total = await TimesheetRepository.get_daily_total_hours(db, user_id, timesheet_date)
            if existing_total + new_hours > max_hours:
                raise BadRequestException(
                    detail=f"You are on partial leave ({leave.partial_start_time}–{leave.partial_end_time}) "
                           f"on {timesheet_date}. Maximum allowed hours: {max_hours:.1f}h. "
                           f"You have already logged {existing_total}h and are trying to add {new_hours}h."
                )

