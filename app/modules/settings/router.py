from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.modules.users.model import User
from app.modules.settings.schema import SystemSettingsSchema, SystemSettingsUpdate
from app.modules.settings.service import SystemSettingsService

router = APIRouter()

@router.get(
    "",
    response_model=dict,
    summary="Get system settings",
)
async def get_settings(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await SystemSettingsService.get_settings(db)
    return success_response(
        data=settings.model_dump(mode="json"),
        message="System settings retrieved successfully",
    )


@router.put(
    "",
    response_model=dict,
    summary="Update system settings",
)
async def update_settings(
    settings_update: SystemSettingsUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    settings = await SystemSettingsService.update_settings(db, settings_update)
    return success_response(
        data=settings.model_dump(mode="json"),
        message="System settings updated successfully",
    )
