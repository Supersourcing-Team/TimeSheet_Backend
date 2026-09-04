"""
Utilization Router — API endpoints for Employee Utilization & Project Cost Control.

Endpoints:
  GET /utilization/dashboard   → KPI cards (capacity, cost, budget, forecast)
  GET /utilization/employees   → Employee-level utilization table
  GET /utilization/milestones  → Milestone-level cost & utilization table
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.common.responses import success_response
from app.modules.users.model import User
from app.modules.utilization.service import UtilizationService
from app.modules.utilization.schema import (
    UtilizationDashboardResponse,
    EmployeeUtilizationResponse,
    MilestoneUtilizationResponse,
)

ac_or_admin = require_roles("Account_Manager", "Admin")

router = APIRouter()


@router.get("/dashboard", response_model=dict, dependencies=[Depends(ac_or_admin)])
async def get_utilization_dashboard(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    milestone_id: Optional[int] = Query(None, description="Filter by milestone"),
    milestone_status: Optional[str] = Query(None, description="Filter by milestone status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """KPI dashboard: capacity, cost, budget, and forecast aggregates."""
    service = UtilizationService(db)
    data = await service.get_dashboard(project_id, milestone_id, milestone_status)
    return success_response(data=data.model_dump(), message="Utilization dashboard loaded")


@router.get("/employees", response_model=dict, dependencies=[Depends(ac_or_admin)])
async def get_employee_utilization(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    milestone_id: Optional[int] = Query(None, description="Filter by milestone"),
    milestone_status: Optional[str] = Query(None, description="Filter by milestone status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee-level utilization breakdown."""
    service = UtilizationService(db)
    data = await service.get_employee_utilization(project_id, milestone_id, milestone_status)
    return success_response(data=data.model_dump(), message="Employee utilization loaded")


@router.get("/milestones", response_model=dict, dependencies=[Depends(ac_or_admin)])
async def get_milestone_utilization(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    milestone_id: Optional[int] = Query(None, description="Filter by milestone"),
    milestone_status: Optional[str] = Query(None, description="Filter by milestone status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Milestone-level cost and utilization breakdown."""
    service = UtilizationService(db)
    data = await service.get_milestone_utilization(project_id, milestone_id, milestone_status)
    return success_response(data=data.model_dump(), message="Milestone utilization loaded")
