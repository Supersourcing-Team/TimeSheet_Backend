from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import create_pagination_data
from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.modules.timesheets.schema import (
    TimesheetCreate,
    TimesheetResponse,
    TimesheetUpdate,
)
from app.dependencies.permissions import require_roles
from app.modules.timesheets.service import TimesheetService

router = APIRouter()


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create a daily timesheet entry")
async def create_timesheet(
    timesheet_in: TimesheetCreate,
    current_user: User = Depends(require_roles("Employee", "Admin")),
    db: AsyncSession = Depends(get_db),
):
    timesheet = await TimesheetService.create_timesheet(db, current_user, timesheet_in)
    resp = TimesheetResponse.model_validate(timesheet)
    return created_response(
        data=resp.model_dump(mode="json"),
        message="Timesheet entry created successfully",
    )


@router.get("/me", response_model=dict, summary="Get logged timesheets for current user")
async def get_my_timesheets(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    project_assignment_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    entries, total = await TimesheetService.get_my_timesheets(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        project_assignment_id=project_assignment_id,
        page=page,
        limit=limit,
    )
    items = []
    for e in entries:
        dump = TimesheetResponse.model_validate(e).model_dump(mode="json")
        dump["user_name"] = e.user_name
        dump["user_avatar"] = e.user_avatar
        dump["project_name"] = e.project_name
        items.append(dump)
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="My timesheet entries retrieved successfully",
    )


@router.get("/managed", response_model=dict, summary="Get timesheets for projects managed by current PM")
async def get_managed_timesheets(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    project_assignment_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles("Project_Manager")),
    db: AsyncSession = Depends(get_db),
):
    entries, total = await TimesheetService.get_managed_timesheets(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        project_assignment_id=project_assignment_id,
        page=page,
        limit=limit,
    )
    items = []
    for e in entries:
        dump = TimesheetResponse.model_validate(e).model_dump(mode="json")
        dump["user_name"] = e.user_name
        dump["user_avatar"] = e.user_avatar
        dump["project_name"] = e.project_name
        items.append(dump)
    paginated_data = create_pagination_data(items=items, total=total, page=page, limit=limit)
    return success_response(
        data=paginated_data,
        message="Managed timesheet entries retrieved successfully",
    )


@router.get("/weekly-summary", response_model=dict, summary="Get 7-day weekly breakdown")
async def get_weekly_summary(
    target_date: Optional[date] = Query(None, description="Any date in the requested target week"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await TimesheetService.get_weekly_summary(db, current_user, target_date=target_date)
    return success_response(
        data=summary.model_dump(mode="json"),
        message="Weekly timesheet summary retrieved successfully",
    )


@router.get("/{timesheet_id}", response_model=dict, summary="Get timesheet entry by ID")
async def get_timesheet_by_id(
    timesheet_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await TimesheetService.get_timesheet_by_id(db, timesheet_id, current_user)
    resp = TimesheetResponse.model_validate(entry)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Timesheet entry retrieved successfully",
    )


@router.put("/{timesheet_id}", response_model=dict, summary="Update an unlocked timesheet entry")
async def update_timesheet(
    timesheet_id: int,
    timesheet_in: TimesheetUpdate,
    current_user: User = Depends(require_roles("Employee", "Admin")),
    db: AsyncSession = Depends(get_db),
):
    updated_entry = await TimesheetService.update_timesheet(db, timesheet_id, current_user, timesheet_in)
    resp = TimesheetResponse.model_validate(updated_entry)
    return success_response(
        data=resp.model_dump(mode="json"),
        message="Timesheet entry updated successfully",
    )



@router.delete("/{timesheet_id}", response_model=dict, summary="Delete a timesheet entry")
async def delete_timesheet(
    timesheet_id: int,
    current_user: User = Depends(require_roles("Employee", "Admin")),
    db: AsyncSession = Depends(get_db),
):
    await TimesheetService.delete_timesheet(db, timesheet_id, current_user)
    return success_response(
        data=None,
        message="Timesheet entry deleted successfully",
    )
