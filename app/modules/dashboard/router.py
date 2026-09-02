from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.modules.users.model import User
from app.modules.dashboard.service import DashboardService

router = APIRouter()

@router.get(
    "/summary",
    response_model=dict,
    summary="Get aggregated dashboard summary",
)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await DashboardService.get_summary(db, current_user)
    return success_response(
        data=summary.model_dump(mode="json"),
        message="Dashboard summary retrieved successfully",
    )
