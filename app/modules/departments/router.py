from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.modules.departments.schema import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.modules.departments.service import DepartmentService
from app.modules.users.model import User

router = APIRouter()


@router.post("", summary="Create a new department (Admin only)", status_code=status.HTTP_201_CREATED)
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    service = DepartmentService(db)
    dept = await service.create_department(data)
    return created_response(
        data=dept.model_dump(mode="json"),
        message="Department created successfully",
    )


@router.get("", summary="List departments")
async def get_departments(
    active_only: bool = Query(True, description="Filter only active departments"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = DepartmentService(db)
    departments = await service.get_all_departments(active_only=active_only)
    return success_response(
        data=[d.model_dump(mode="json") for d in departments],
        message="Departments retrieved successfully",
    )


@router.get("/{department_id}", summary="Get department by ID")
async def get_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = DepartmentService(db)
    dept = await service.get_department(department_id)
    return success_response(
        data=dept.model_dump(mode="json"),
        message="Department retrieved successfully",
    )


@router.put("/{department_id}", summary="Update a department (Admin only)")
async def update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    service = DepartmentService(db)
    dept = await service.update_department(department_id, data)
    return success_response(
        data=dept.model_dump(mode="json"),
        message="Department updated successfully",
    )


@router.delete("/{department_id}", summary="Delete a department (Admin only)")
async def delete_department(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    service = DepartmentService(db)
    await service.delete_department(department_id)
    return success_response(message="Department deleted successfully")
