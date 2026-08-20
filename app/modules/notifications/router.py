from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.modules.notifications.service import NotificationService

router = APIRouter()


@router.get("", response_model=dict, summary="Get notifications for the current user")
async def get_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a list of real-time notifications derived from:
    - Own leave request status changes (approved / rejected)
    - Own weekend work status changes (approved / rejected)
    - Pending leave requests awaiting review (Admin / PM / Account Manager only)
    - Pending weekend work requests awaiting review (Admin / PM / Account Manager only)
    """
    result = await NotificationService.get_notifications(db, current_user)
    return success_response(
        data=result.model_dump(mode="json"),
        message="Notifications retrieved successfully",
    )
