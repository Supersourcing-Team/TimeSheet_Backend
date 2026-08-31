from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.modules.leave_balances.repository import LeaveBalanceRepository
from app.modules.leave_requests.repository import LeaveRequestRepository
from app.modules.leave_requests.schema import LeaveRequestReview, LeaveRequestSubmit
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
