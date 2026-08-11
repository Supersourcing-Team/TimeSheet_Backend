from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.models.user import User
from app.modules.leave_types.schema import LeaveTypeCreate, LeaveTypeResponse, LeaveTypeUpdate
from app.modules.leave_types.service import LeaveTypeService

router = APIRouter()


@router.get("", summary="Get active leave categories")
async def get_leave_types(
    active_only: bool = Query(True, description="Filter active leave categories"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    leave_types = await LeaveTypeService.get_leave_types(db, active_only=active_only)
    result = [LeaveTypeResponse.model_validate(lt).model_dump(mode="json") for lt in leave_types]
    return success_response(data=result, message="Leave types retrieved successfully")


@router.post("", summary="Create leave category (Admin)")
async def create_leave_type(
    request: LeaveTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leave_type = await LeaveTypeService.create_leave_type(db, request)
    result = LeaveTypeResponse.model_validate(leave_type).model_dump(mode="json")
    return created_response(data=result, message="Leave type created successfully")


@router.put("/{leave_type_id}", summary="Update leave category (Admin)")
async def update_leave_type(
    leave_type_id: int,
    request: LeaveTypeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leave_type = await LeaveTypeService.update_leave_type(db, leave_type_id, request)
    result = LeaveTypeResponse.model_validate(leave_type).model_dump(mode="json")
    return success_response(data=result, message="Leave type updated successfully")


@router.delete("/{leave_type_id}", summary="Soft delete/deactivate leave category (Admin)")
async def delete_leave_type(
    leave_type_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leave_type = await LeaveTypeService.delete_leave_type(db, leave_type_id)
    result = LeaveTypeResponse.model_validate(leave_type).model_dump(mode="json")
    return success_response(data=result, message="Leave type deactivated successfully")
