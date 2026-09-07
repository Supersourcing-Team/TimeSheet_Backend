from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.modules.users.model import User
from app.modules.weekend_work.model import WeekendWorkRequest
from app.modules.weekend_work.repository import WeekendWorkRepository
from app.modules.weekend_work.schema import WeekendWorkReview, WeekendWorkSubmit
from app.modules.weekend_work.validator import WeekendWorkValidator


class WeekendWorkService:
    """Service handling business logic for Weekend Work Overtime Requests."""

    @staticmethod
    async def submit_weekend_work(
        db: AsyncSession,
        current_user: User,
        request_in: WeekendWorkSubmit,
    ) -> WeekendWorkRequest:
        # 1. Validate date is a Saturday, Sunday, or official public holiday
        await WeekendWorkValidator.validate_weekend_or_holiday_date(db, request_in.work_date)

        # 2. Validate project assignment ownership
        await WeekendWorkValidator.validate_project_assignment(
            db, current_user.id, request_in.project_assignment_id
        )

        # 3. Check for existing pending or approved request on same assignment & date
        existing = await WeekendWorkRepository.get_by_assignment_and_date(
            db, request_in.project_assignment_id, request_in.work_date
        )
        if existing:
            raise ConflictException(
                detail=f"A weekend work request already exists for this project on {request_in.work_date}."
            )

        # 4. Create record
        total_hours = (
            request_in.planned_hours
            if request_in.planned_hours is not None and request_in.planned_hours > 0
            else (request_in.billable_hours + request_in.non_billable_hours)
        )
        if total_hours <= 0:
            total_hours = 8.0

        weekend_request = WeekendWorkRequest(
            project_assignment_id=request_in.project_assignment_id,
            work_date=request_in.work_date,
            planned_hours=total_hours,
            billable_hours=request_in.billable_hours,
            billable_work_summary=request_in.billable_work_summary,
            non_billable_hours=request_in.non_billable_hours,
            non_billable_work_summary=request_in.non_billable_work_summary,
            reason=request_in.reason,
            status="Pending",
        )
        return await WeekendWorkRepository.create(db, weekend_request)

    @staticmethod
    async def get_my_weekend_work_requests(
        db: AsyncSession,
        current_user: User,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WeekendWorkRequest], int]:
        return await WeekendWorkRepository.list_by_user(
            db, current_user.id, status=status, page=page, limit=limit
        )

    @staticmethod
    async def get_requests_for_pm(
        db: AsyncSession,
        pm_user: User,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WeekendWorkRequest], int]:
        is_admin = getattr(pm_user.role, "name", None) == "Admin"
        if is_admin:
            return await WeekendWorkRepository.list_all(db, status=status, page=page, limit=limit)

        return await WeekendWorkRepository.list_for_pm(
            db, pm_user.id, status=status, page=page, limit=limit
        )

    @staticmethod
    async def approve_weekend_work(
        db: AsyncSession,
        request_id: int,
        pm_user: User,
    ) -> WeekendWorkRequest:
        request = await WeekendWorkRepository.get_by_id(db, request_id)
        if not request:
            raise NotFoundException(detail="Weekend work request not found.")

        if request.status != "Pending":
            raise ConflictException(
                detail=f"Cannot approve request with status '{request.status}'."
            )

        # Check authorization: Admin or assigned PM for the project
        is_admin = getattr(pm_user.role, "name", None) == "Admin"
        project_pm_id = getattr(request.project_assignment.project, "project_manager_id", None)

        if not is_admin and project_pm_id != pm_user.id:
            raise ForbiddenException(
                detail="Only the Project Manager assigned to this project can approve weekend work."
            )

        approved_request = await WeekendWorkRepository.update_status(
            db, request, status="Approved", approver_id=pm_user.id
        )

        # Automatically insert or update Timesheet record
        from sqlalchemy import and_, select
        from app.modules.timesheets.model import Timesheet

        user_id = request.project_assignment.user_id
        project_assignment_id = request.project_assignment_id
        work_date = request.work_date

        stmt = select(Timesheet).where(
            and_(
                Timesheet.user_id == user_id,
                Timesheet.project_assignment_id == project_assignment_id,
                Timesheet.timesheet_date == work_date,
            )
        )
        res = await db.execute(stmt)
        existing_timesheet = res.scalars().first()

        if existing_timesheet:
            existing_timesheet.billable_hours = request.billable_hours
            existing_timesheet.billable_work_summary = request.billable_work_summary or request.reason
            existing_timesheet.non_billable_hours = request.non_billable_hours
            existing_timesheet.non_billable_work_summary = request.non_billable_work_summary
            existing_timesheet.status = "approved"
        else:
            new_timesheet = Timesheet(
                user_id=user_id,
                project_assignment_id=project_assignment_id,
                timesheet_date=work_date,
                billable_hours=request.billable_hours,
                billable_work_summary=request.billable_work_summary or request.reason,
                non_billable_hours=request.non_billable_hours,
                non_billable_work_summary=request.non_billable_work_summary,
                status="approved",
            )
            db.add(new_timesheet)

        await db.commit()
        return approved_request

    @staticmethod
    async def reject_weekend_work(
        db: AsyncSession,
        request_id: int,
        pm_user: User,
        review_in: WeekendWorkReview,
    ) -> WeekendWorkRequest:
        request = await WeekendWorkRepository.get_by_id(db, request_id)
        if not request:
            raise NotFoundException(detail="Weekend work request not found.")

        if request.status != "Pending":
            raise ConflictException(
                detail=f"Cannot reject request with status '{request.status}'."
            )

        # Check authorization: Admin or assigned PM for the project
        is_admin = getattr(pm_user.role, "name", None) == "Admin"
        project_pm_id = getattr(request.project_assignment.project, "project_manager_id", None)

        if not is_admin and project_pm_id != pm_user.id:
            raise ForbiddenException(
                detail="Only the Project Manager assigned to this project can reject weekend work."
            )

        return await WeekendWorkRepository.update_status(
            db, request, status="Rejected", approver_id=pm_user.id
        )

    @staticmethod
    async def cancel_weekend_work(
        db: AsyncSession,
        request_id: int,
        current_user: User,
    ) -> WeekendWorkRequest:
        request = await WeekendWorkRepository.get_by_id(db, request_id)
        if not request:
            raise NotFoundException(detail="Weekend work request not found.")

        is_admin = getattr(current_user.role, "name", None) == "Admin"
        owner_id = request.project_assignment.user_id

        if owner_id != current_user.id and not is_admin:
            raise ForbiddenException(detail="You do not have permission to cancel this weekend work request.")

        if request.status == "Cancelled":
            raise ConflictException(detail="Request is already cancelled.")

        return await WeekendWorkRepository.update_status(
            db, request, status="Cancelled"
        )
