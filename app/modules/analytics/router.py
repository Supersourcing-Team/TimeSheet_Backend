from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User
from app.modules.analytics.service import AnalyticsService

router = APIRouter()
pm_or_admin_or_ac = require_roles("Admin", "Project_Manager", "Account_Manager")

@router.get(
    "/team-utilization",
    response_model=dict,
    dependencies=[Depends(pm_or_admin_or_ac)],
    summary="Get aggregated team utilization metrics",
)
async def get_team_utilization(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await AnalyticsService.get_team_utilization(db, current_user)
    return success_response(
        data=summary.model_dump(mode="json"),
        message="Team utilization metrics retrieved successfully",
    )


@router.get(
    "/project-financials",
    response_model=dict,
    dependencies=[Depends(pm_or_admin_or_ac)],
    summary="Get aggregated project financials",
)
async def get_project_financials(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await AnalyticsService.get_project_financials(db, current_user)
    return success_response(
        data=summary.model_dump(mode="json"),
        message="Project financials retrieved successfully",
    )
