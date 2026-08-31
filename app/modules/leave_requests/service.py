from datetime import date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.modules.leave_balances.repository import LeaveBalanceRepository
from app.modules.leave_requests.repository import LeaveRequestRepository
from app.modules.leave_requests.schema import LeaveCheckDateResponse, LeaveMarkFromTimesheetRequest, LeaveRequestReview, LeaveRequestSubmit
from app.modules.leave_requests.validator import LeaveRequestValidator
from app.modules.leave_types.repository import LeaveTypeRepository
from app.services.email_service import send_leave_approved_email, send_leave_rejected_email



class LeaveRequestService:
    """Service handling business logic for Leave Requests."""

    @staticmethod
    async def submit_leave_request(
        db: AsyncSession,
        current_user: User,
        request_in: LeaveRequestSubmit,
    ) -> LeaveRequest:
        # 1. Check leave type exists and is active
        leave_type = await LeaveTypeRepository.get_by_id(db, request_in.leave_type_id)
        if not leave_type or not leave_type.is_active:
            raise BadRequestException(detail="Invalid or inactive leave type.")

        # 2. Validate dates & calculate required working days
        working_days = await LeaveRequestValidator.calculate_working_days(
            db, request_in.start_date, request_in.end_date
        )
        if working_days <= 0:
            raise BadRequestException(
                detail="Selected date range contains no working days (all weekends or public holidays)."
            )

        # 3. Check available leave balance for the year of start_date (dynamically referencing Admin LeaveType)
        year = request_in.start_date.year
        balance = await LeaveBalanceRepository.get_specific_balance(
            db, current_user.id, request_in.leave_type_id, year
        )
        if balance:
            allocated_days = balance.allocated_days
            used_days = balance.used_days
        else:
            allocated_days = float(leave_type.days_per_year) if (leave_type and leave_type.days_per_year is not None) else 0.0
            used_days = 0.0

        available_days = allocated_days - used_days
        if working_days > available_days:
            raise BadRequestException(
                detail=f"Insufficient leave balance. Required: {working_days} day(s), Available: {available_days} day(s)."
            )



        # 4. Create LeaveRequest record
        leave_request = LeaveRequest(
            user_id=current_user.id,
            leave_type_id=request_in.leave_type_id,
            start_date=request_in.start_date,
            end_date=request_in.end_date,
            reason=request_in.reason,
            status="Pending",
        )
        return await LeaveRequestRepository.create(db, leave_request)

    @staticmethod
    async def get_my_leave_requests(
        db: AsyncSession,
        current_user: User,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[LeaveRequest], int]:
        return await LeaveRequestRepository.list_by_user(
            db, current_user.id, status=status, page=page, limit=limit
        )

    @staticmethod
    async def list_all_leave_requests(
        db: AsyncSession,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[LeaveRequest], int]:
        return await LeaveRequestRepository.list_all(
            db, status=status, user_id=user_id, page=page, limit=limit
        )

    @staticmethod
    async def get_upcoming_team_leaves(
        db: AsyncSession,
        current_user: User,
    ) -> List[LeaveRequest]:
        is_admin = getattr(current_user.role, "name", None) == "Admin"
        user_ids = None
        
        if not is_admin:
            from sqlalchemy.future import select
            from app.models.project import Project
            from app.models.project_assignment import ProjectAssignment
            
            # PM logic: Get projects where user is PM, then get assigned users
            res = await db.execute(
                select(Project).where(Project.project_manager_id == current_user.id)
            )
            pm_projects = res.scalars().all()
            project_ids = [p.id for p in pm_projects]
            
            if project_ids:
                assign_res = await db.execute(
                    select(ProjectAssignment.user_id).where(
                        ProjectAssignment.project_id.in_(project_ids),
                        ProjectAssignment.is_active == True
                    )
                )
                user_ids = [row for row in assign_res.scalars().all()]
            else:
                user_ids = []
                
            # also include PM themselves
            user_ids.append(current_user.id)
            user_ids = list(set(user_ids))
            
        return await LeaveRequestRepository.get_upcoming_team_leaves(db, user_ids, is_admin)

    @staticmethod
    async def approve_leave_request(
        db: AsyncSession,
        request_id: int,
        admin_user: User,
    ) -> LeaveRequest:
        leave_request = await LeaveRequestRepository.get_by_id(db, request_id)
        if not leave_request:
            raise NotFoundException(detail="Leave request not found.")

        if leave_request.status != "Pending":
            raise ConflictException(
                detail=f"Cannot approve leave request with status '{leave_request.status}'."
            )

        # Calculate working days to deduct
        working_days = await LeaveRequestValidator.calculate_working_days(
            db, leave_request.start_date, leave_request.end_date
        )

        year = leave_request.start_date.year
        balance = await LeaveBalanceRepository.get_specific_balance(
            db, leave_request.user_id, leave_request.leave_type_id, year
        )
        if not balance:
            leave_type = await LeaveTypeRepository.get_by_id(db, leave_request.leave_type_id)
            alloc = float(leave_type.days_per_year) if (leave_type and leave_type.days_per_year is not None) else 0.0
            balance = await LeaveBalanceRepository.create(
                db,
                user_id=leave_request.user_id,
                leave_type_id=leave_request.leave_type_id,
                year=year,
                allocated_days=alloc,
            )


        # Deduct used days
        balance.used_days += working_days
        await db.commit()


        # Update leave request status to Approved
        updated_request = await LeaveRequestRepository.update_status(
            db, leave_request, status="Approved", manager_id=admin_user.id
        )

        # Dispatch Leave Approved Email Notification
        if updated_request.user and updated_request.user.email:
            user_full_name = f"{updated_request.user.first_name} {updated_request.user.last_name}".strip()
            approver_full_name = f"{admin_user.first_name} {admin_user.last_name}".strip()
            leave_type_name = updated_request.leave_type.name if updated_request.leave_type else "Leave"
            await send_leave_approved_email(
                to_email=updated_request.user.email,
                user_name=user_full_name,
                leave_type=leave_type_name,
                start_date=str(updated_request.start_date),
                end_date=str(updated_request.end_date),
                working_days=working_days,
                approver_name=approver_full_name,
            )

        return updated_request

    @staticmethod
    async def reject_leave_request(
        db: AsyncSession,
        request_id: int,
        admin_user: User,
        review_in: LeaveRequestReview,
    ) -> LeaveRequest:
        leave_request = await LeaveRequestRepository.get_by_id(db, request_id)
        if not leave_request:
            raise NotFoundException(detail="Leave request not found.")

        if leave_request.status != "Pending":
            raise ConflictException(
                detail=f"Cannot reject leave request with status '{leave_request.status}'."
            )

        updated_request = await LeaveRequestRepository.update_status(
            db,
            leave_request,
            status="Rejected",
            manager_id=admin_user.id,
            rejection_reason=review_in.rejection_reason,
        )

        # Dispatch Leave Rejected Email Notification
        if updated_request.user and updated_request.user.email:
            user_full_name = f"{updated_request.user.first_name} {updated_request.user.last_name}".strip()
            reviewer_full_name = f"{admin_user.first_name} {admin_user.last_name}".strip()
            leave_type_name = updated_request.leave_type.name if updated_request.leave_type else "Leave"
            await send_leave_rejected_email(
                to_email=updated_request.user.email,
                user_name=user_full_name,
                leave_type=leave_type_name,
                start_date=str(updated_request.start_date),
                end_date=str(updated_request.end_date),
                rejection_reason=review_in.rejection_reason,
                reviewer_name=reviewer_full_name,
            )

        return updated_request


    @staticmethod
    async def cancel_leave_request(
        db: AsyncSession,
        request_id: int,
        current_user: User,
    ) -> LeaveRequest:
        leave_request = await LeaveRequestRepository.get_by_id(db, request_id)
        if not leave_request:
            raise NotFoundException(detail="Leave request not found.")

        # Non-admin users can only cancel their own requests
        is_admin = getattr(current_user.role, "name", None) == "Admin"
        if leave_request.user_id != current_user.id and not is_admin:
            raise ForbiddenException(detail="You do not have permission to cancel this leave request.")

        if leave_request.status == "Cancelled":
            raise ConflictException(detail="Leave request is already cancelled.")

        # If it was Approved, refund the balance
        if leave_request.status == "Approved":
            working_days = await LeaveRequestValidator.calculate_working_days(
                db, leave_request.start_date, leave_request.end_date
            )
            year = leave_request.start_date.year
            balance = await LeaveBalanceRepository.get_specific_balance(
                db, leave_request.user_id, leave_request.leave_type_id, year
            )
            if balance:
                balance.used_days = max(0, balance.used_days - working_days)
                await db.commit()

        return await LeaveRequestRepository.update_status(
            db, leave_request, status="Cancelled"
        )

    # -------------------------------------------------------------------------
    # Inline Mark-Leave from Timesheet
    # -------------------------------------------------------------------------

    @staticmethod
    async def mark_leave_from_timesheet(
        db: AsyncSession,
        current_user: User,
        request_in: LeaveMarkFromTimesheetRequest,
    ) -> List[LeaveRequest]:
        """
        Mark leave directly from the timesheet UI.
        Returns a list of created LeaveRequest records (one per day for multiple_days).
        Leave is auto-Approved; balance is deducted immediately.
        """
        duration = request_in.leave_duration_type

        # 1. Validate leave type
        if request_in.leave_type_id:
            leave_type = await LeaveTypeRepository.get_by_id(db, request_in.leave_type_id)
            if not leave_type or not leave_type.is_active:
                raise BadRequestException(detail="Invalid or inactive leave type.")
        else:
            # Fallback for half_day/partial_day where type might not be selected
            all_types = await LeaveTypeRepository.get_all(db, active_only=True)
            if all_types:
                leave_type = all_types[0]
                request_in.leave_type_id = leave_type.id
            else:
                # Auto-create fallback General Leave
                leave_type = await LeaveTypeRepository.create(
                    db,
                    name="General Leave",
                    code="GENERAL",
                    is_active=True,
                )
                request_in.leave_type_id = leave_type.id

        created_records: List[LeaveRequest] = []

        # ---- Multiple Days ----
        if duration == "multiple_days":
            if not request_in.start_date or not request_in.end_date:
                raise BadRequestException(detail="start_date and end_date are required for multiple_days leave.")
            if request_in.start_date > request_in.end_date:
                raise BadRequestException(detail="start_date must be before end_date.")
            if request_in.end_date > date.today():
                raise BadRequestException(detail="Cannot mark leave for future dates.")

            # Iterate each working day in the range
            current = request_in.start_date
            while current <= request_in.end_date:
                if current.weekday() not in (5, 6):  # Skip weekends
                    # Check for duplicate leave on this day
                    await LeaveRequestValidator.validate_no_duplicate_leave(db, current_user.id, current)
                    # Check timesheet conflict
                    await LeaveRequestValidator.validate_no_timesheet_conflict(
                        db, current_user.id, current, "full_day"
                    )
                    # Deduct balance (0.5 day per day worked)
                    year = current.year
                    balance = await LeaveBalanceRepository.get_specific_balance(
                        db, current_user.id, request_in.leave_type_id, year
                    )
                    if balance:
                        if balance.allocated_days - balance.used_days < 1:
                            raise BadRequestException(
                                detail=f"Insufficient leave balance on {current}. "
                                       f"Available: {balance.allocated_days - balance.used_days:.1f} day(s)."
                            )

                    leave_record = LeaveRequest(
                        user_id=current_user.id,
                        leave_type_id=request_in.leave_type_id,
                        start_date=current,
                        end_date=current,
                        reason=request_in.reason or "Marked from timesheet",
                        status="Approved",
                        leave_duration_type="full_day",
                    )
                    saved = await LeaveRequestRepository.create(db, leave_record)
                    created_records.append(saved)

                    # Deduct balance for this day
                    if balance:
                        balance.used_days += 1.0
                        await db.commit()

                current += timedelta(days=1)

            return created_records

        # ---- Single Day Leaves ----
        leave_date = request_in.leave_date
        if not leave_date:
            raise BadRequestException(detail="leave_date is required for single-day leaves.")
        if leave_date > date.today():
            raise BadRequestException(detail="Cannot mark leave for future dates.")

        # Partial day extra validation
        if duration == "partial_day":
            LeaveRequestValidator.validate_partial_time(
                request_in.partial_start_time, request_in.partial_end_time
            )

        # Half day requires period
        if duration == "half_day" and not request_in.half_day_period:
            raise BadRequestException(detail="half_day_period ('first' or 'second') is required for half_day leave.")

        # Duplicate leave check
        await LeaveRequestValidator.validate_no_duplicate_leave(db, current_user.id, leave_date)

        # Timesheet conflict check
        await LeaveRequestValidator.validate_no_timesheet_conflict(
            db,
            current_user.id,
            leave_date,
            duration,
            request_in.partial_start_time,
            request_in.partial_end_time,
        )

        # Check and deduct leave balance
        year = leave_date.year
        balance = await LeaveBalanceRepository.get_specific_balance(
            db, current_user.id, request_in.leave_type_id, year
        )
        if not balance:
            alloc = float(leave_type.days_per_year) if leave_type.days_per_year else 0.0
            balance = await LeaveBalanceRepository.create(
                db,
                user_id=current_user.id,
                leave_type_id=request_in.leave_type_id,
                year=year,
                allocated_days=alloc,
            )

        # Determine deduction
        if duration == "full_day":
            deduction = 1.0
        elif duration == "half_day":
            deduction = 0.5
        else:  # partial_day
            start_h, start_m = map(int, request_in.partial_start_time.split(":"))
            end_h, end_m = map(int, request_in.partial_end_time.split(":"))
            leave_hours = (end_h * 60 + end_m - start_h * 60 - start_m) / 60.0
            deduction = leave_hours / 8.0  # fraction of a day

        available = (balance.allocated_days or 0) - (balance.used_days or 0)
        if available < deduction:
            raise BadRequestException(
                detail=f"Insufficient leave balance. Required: {deduction:.2f} day(s), Available: {available:.2f} day(s)."
            )

        # Create the leave record
        leave_record = LeaveRequest(
            user_id=current_user.id,
            leave_type_id=request_in.leave_type_id,
            start_date=leave_date,
            end_date=leave_date,
            reason=request_in.reason or "Marked from timesheet",
            status="Approved",
            leave_duration_type=duration,
            half_day_period=request_in.half_day_period,
            partial_start_time=request_in.partial_start_time,
            partial_end_time=request_in.partial_end_time,
        )
        saved = await LeaveRequestRepository.create(db, leave_record)

        # Deduct balance
        balance.used_days += deduction
        await db.commit()

        return [saved]

    @staticmethod
    async def check_leave_for_date(
        db: AsyncSession,
        current_user: User,
        check_date: date,
    ) -> LeaveCheckDateResponse:
        """
        Return a structured leave status object for a specific date.
        The frontend uses this to block/enable timesheet inputs.
        """
        leaves = await LeaveRequestRepository.get_approved_leaves_for_date(db, current_user.id, check_date)

        if not leaves:
            return LeaveCheckDateResponse(date=check_date, has_leave=False, available_hours=8.0)

        # Pick the first (most recently relevant) leave
        leave = leaves[0]
        duration = leave.leave_duration_type or "full_day"
        leave_type_name = leave.leave_type.name if leave.leave_type else "Leave"

        # Calculate available hours and blocked message
        if duration == "full_day":
            available_hours = 0.0
            blocked_message = "On Leave – Full Day"
        elif duration == "half_day":
            available_hours = 4.0
            period_label = "First Half" if leave.half_day_period == "first" else "Second Half"
            blocked_message = f"On Leave – {period_label}"
        elif duration == "partial_day":
            start_h, start_m = map(int, leave.partial_start_time.split(":"))
            end_h, end_m = map(int, leave.partial_end_time.split(":"))
            leave_hours = (end_h * 60 + end_m - start_h * 60 - start_m) / 60.0
            available_hours = max(0.0, 8.0 - leave_hours)
            # Format times for display
            def fmt_time(hh: int, mm: int) -> str:
                suffix = "AM" if hh < 12 else "PM"
                display_h = hh if hh <= 12 else hh - 12
                if display_h == 0:
                    display_h = 12
                return f"{display_h}:{mm:02d} {suffix}"
            blocked_message = (
                f"On Leave – {fmt_time(start_h, start_m)} – {fmt_time(end_h, end_m)}"
            )
        else:
            available_hours = 0.0
            blocked_message = "On Leave"

        return LeaveCheckDateResponse(
            date=check_date,
            has_leave=True,
            leave_duration_type=duration,
            half_day_period=leave.half_day_period,
            partial_start_time=leave.partial_start_time,
            partial_end_time=leave.partial_end_time,
            leave_id=leave.id,
            leave_type_name=leave_type_name,
            available_hours=available_hours,
            blocked_message=blocked_message,
        )



