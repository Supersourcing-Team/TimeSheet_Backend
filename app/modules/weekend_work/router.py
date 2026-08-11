from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import create_pagination_data
from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User
from app.modules.weekend_work.schema import (
    WeekendWorkResponse,
    WeekendWorkReview,
    WeekendWorkSubmit,
)
from app.modules.weekend_work.service import WeekendWorkService

router = APIRouter()
pm_or_admin = require_roles("Project_Manager", "Admin")


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Submit weekend work overtime request")
async def submit_weekend_work(
    request_in: WeekendWorkSubmit,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    request = await WeekendWorkService.submit_weekend_work(db, current_user, request_in)
    resp = WeekendWorkResponse.model_validate(request)
    return created_response(
        data=resp.model_dump(mode="json"),
        message="Weekend work request submitted successfully",
    )


@router.get("/me", response_model=dict, summary="Get my weekend work requests")
async def get_my_weekend_work_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    requests, total = await WeekendWorkService.get_my_weekend_work_requests(
        db, current_user, status=status_filter, page=page, limit=limit
    )
    items = [WeekendWorkResponse.model_validate(r).model_dump(mode="json") for r in requests]
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="My weekend work requests retrieved successfully",
    )


@router.get("/pending", response_model=dict, dependencies=[Depends(pm_or_admin)], summary="Get pending weekend work requests for PM's projects")
async def get_pending_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    requests, total = await WeekendWorkService.get_pending_requests_for_pm(
        db, current_user, page=page, limit=limit
    )
    items = [WeekendWorkResponse.model_validate(r).model_dump(mode="json") for r in requests]
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="Pending weekend work requests retrieved successfully",
    )


@router.put("/{request_id}/approve", response_model=dict, dependencies=[Depends(pm_or_admin)], summary="Approve weekend work request (PM/Admin)")
async def approve_weekend_work(
    request_id: int,
    pm_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    request = await WeekendWorkService.approve_weekend_work(db, request_id, pm_user)
    resp = WeekendWorkResponse.model_validate(request)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Weekend work request approved successfully",
    )


@router.put("/{request_id}/reject", response_model=dict, dependencies=[Depends(pm_or_admin)], summary="Reject weekend work request (PM/Admin)")
async def reject_weekend_work(
    request_id: int,
    review_in: WeekendWorkReview,
    pm_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    request = await WeekendWorkService.reject_weekend_work(db, request_id, pm_user, review_in)
    resp = WeekendWorkResponse.model_validate(request)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Weekend work request rejected successfully",
    )


@router.delete("/{request_id}/cancel", response_model=dict, summary="Cancel pending weekend work request")
async def cancel_weekend_work(
    request_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    request = await WeekendWorkService.cancel_weekend_work(db, request_id, current_user)
    resp = WeekendWorkResponse.model_validate(request)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Weekend work request cancelled successfully",
    )
