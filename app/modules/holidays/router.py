from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.modules.users.model import User
from app.modules.holidays.schema import HolidayCreate, HolidayResponse, HolidayUpdate
from app.modules.holidays.service import HolidayService

router = APIRouter()


@router.get("", summary="Get company holidays")
async def get_holidays(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, description="Filter by month"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    holidays = await HolidayService.get_holidays(db, year=year, month=month)
    result = [HolidayResponse.model_validate(h).model_dump(mode="json") for h in holidays]
    return success_response(data=result, message="Holidays retrieved successfully")


@router.post("", summary="Create a new holiday (Admin)")
async def create_holiday(
    request: HolidayCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    holiday = await HolidayService.create_holiday(db, request)
    result = HolidayResponse.model_validate(holiday).model_dump(mode="json")
    return created_response(data=result, message="Holiday created successfully")


@router.put("/{holiday_id}", summary="Update holiday (Admin)")
async def update_holiday(
    holiday_id: int,
    request: HolidayUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    holiday = await HolidayService.update_holiday(db, holiday_id, request)
    result = HolidayResponse.model_validate(holiday).model_dump(mode="json")
    return success_response(data=result, message="Holiday updated successfully")


@router.delete("/{holiday_id}", summary="Delete holiday (Admin)")
async def delete_holiday(
    holiday_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await HolidayService.delete_holiday(db, holiday_id)
    return success_response(data=None, message="Holiday deleted successfully")
