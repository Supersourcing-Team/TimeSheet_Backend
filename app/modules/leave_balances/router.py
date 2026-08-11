from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin, require_project_manager
from app.models.user import User
from app.modules.leave_balances.schema import LeaveBalanceCreate, LeaveBalanceResponse, LeaveBalanceUpdate
from app.modules.leave_balances.service import LeaveBalanceService

router = APIRouter()


@router.get("/me", summary="Get current employee leave balances")
async def get_my_balances(
    year: Optional[int] = Query(None, description="Year filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    balances = await LeaveBalanceService.get_user_balances(db, user_id=current_user.id, year=year)
    result = [b.model_dump(mode="json") for b in balances]
    return success_response(data=result, message="Leave balances retrieved successfully")


@router.get("/user/{user_id}", summary="Get user leave balances (Admin/Manager)")
async def get_user_balances(
    user_id: int,
    year: Optional[int] = Query(None, description="Year filter"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_project_manager),
):
    balances = await LeaveBalanceService.get_user_balances(db, user_id=user_id, year=year)
    result = [b.model_dump(mode="json") for b in balances]
    return success_response(data=result, message="User leave balances retrieved successfully")


@router.post("", summary="Allocate leave days to user (Admin)")
async def allocate_balance(
    request: LeaveBalanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    balance = await LeaveBalanceService.allocate_balance(db, request)
    return created_response(data=balance.model_dump(mode="json"), message="Leave balance allocated successfully")


@router.put("/{balance_id}", summary="Update leave balance allocation (Admin)")
async def update_balance(
    balance_id: int,
    request: LeaveBalanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    balance = await LeaveBalanceService.update_balance(db, balance_id, request)
    return success_response(data=balance.model_dump(mode="json"), message="Leave balance updated successfully")
