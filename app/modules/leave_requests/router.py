from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import create_pagination_data
from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.models.user import User
from app.modules.leave_requests.schema import (
    LeaveCheckDateResponse,
    LeaveMarkFromTimesheetRequest,
    LeaveRequestResponse,
    LeaveRequestReview,
    LeaveRequestSubmit,
)
from app.modules.leave_requests.service import LeaveRequestService

router = APIRouter()


@router.post("/mark-from-timesheet", response_model=dict, status_code=status.HTTP_201_CREATED,
             summary="Mark leave directly from timesheet (auto-approved)")
async def mark_leave_from_timesheet(
    request_in: LeaveMarkFromTimesheetRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    leave_records = await LeaveRequestService.mark_leave_from_timesheet(db, current_user, request_in)
    items = [LeaveRequestResponse.model_validate(r).model_dump(mode="json") for r in leave_records]
    return created_response(
        data=items,
        message=f"Leave marked successfully ({len(items)} record(s) created).",
    )


@router.get("/check-date", response_model=dict, summary="Check leave status for a specific date")
async def check_leave_for_date(
    date: date = Query(..., description="Date to check in YYYY-MM-DD format"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await LeaveRequestService.check_leave_for_date(db, current_user, date)
    return success_response(
        data=result.model_dump(mode="json"),
        message="Leave status for date retrieved successfully.",
    )


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Submit a leave application")
async def submit_leave_request(
    request_in: LeaveRequestSubmit,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    leave_req = await LeaveRequestService.submit_leave_request(db, current_user, request_in)
    resp = LeaveRequestResponse.model_validate(leave_req)
    return created_response(
        data=resp.model_dump(mode="json"),
        message="Leave application submitted successfully",
    )


@router.get("/me", response_model=dict, summary="Get my submitted leave applications")
async def get_my_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    requests, total = await LeaveRequestService.get_my_leave_requests(
        db, current_user, status=status_filter, page=page, limit=limit
    )
    items = [LeaveRequestResponse.model_validate(r).model_dump(mode="json") for r in requests]
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="My leave applications retrieved successfully",
    )


@router.get("", response_model=dict, dependencies=[Depends(require_admin)], summary="List all leave requests (Admin)")
async def list_all_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    requests, total = await LeaveRequestService.list_all_leave_requests(
        db, status=status_filter, user_id=user_id, page=page, limit=limit
    )
    items = [LeaveRequestResponse.model_validate(r).model_dump(mode="json") for r in requests]
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="All leave applications retrieved successfully",
    )


@router.put("/{request_id}/approve", response_model=dict, dependencies=[Depends(require_admin)], summary="Approve leave request (Admin)")
async def approve_leave_request(
    request_id: int,
    admin_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    leave_req = await LeaveRequestService.approve_leave_request(db, request_id, admin_user)
    resp = LeaveRequestResponse.model_validate(leave_req)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Leave application approved successfully",
    )


@router.put("/{request_id}/reject", response_model=dict, dependencies=[Depends(require_admin)], summary="Reject leave request (Admin)")
async def reject_leave_request(
    request_id: int,
    review_in: LeaveRequestReview,
    admin_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    leave_req = await LeaveRequestService.reject_leave_request(db, request_id, admin_user, review_in)
    resp = LeaveRequestResponse.model_validate(leave_req)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Leave application rejected successfully",
    )


@router.delete("/{request_id}/cancel", response_model=dict, summary="Cancel pending/approved leave application")
async def cancel_leave_request(
    request_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    leave_req = await LeaveRequestService.cancel_leave_request(db, request_id, current_user)
    resp = LeaveRequestResponse.model_validate(leave_req)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Leave application cancelled successfully",
    )
