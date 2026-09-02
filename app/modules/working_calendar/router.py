from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.modules.users.model import User
from app.modules.working_calendar.schema import WorkingCalendarResponse, WorkingCalendarUpdate
from app.modules.working_calendar.service import WorkingCalendarService
from app.common.responses import success_response

router = APIRouter()

@router.get("", summary="Get working calendar configuration")
async def get_working_calendar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    config = await WorkingCalendarService.get_config(db)
    result = WorkingCalendarResponse.model_validate(config).model_dump(mode="json")
    return success_response(data=result, message="Working calendar retrieved successfully")

@router.put("", summary="Update working calendar configuration (Admin)")
async def update_working_calendar(
    request: WorkingCalendarUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    config = await WorkingCalendarService.update_config(db, request)
    result = WorkingCalendarResponse.model_validate(config).model_dump(mode="json")
    return success_response(data=result, message="Working calendar updated successfully")
