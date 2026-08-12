from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams, create_paginated_response
from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_admin
from app.models.user import User
from app.modules.users.schema import (
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter()


@router.post("", summary="Create a new user (Admin only)")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Creates a new user record in the system.
    Users cannot self-register; only an Admin can create new users.
    """
    user = await UserService.create_user(db, data)
    user_response = UserResponse.model_validate(user).model_dump(mode='json')
    return created_response(
        data=user_response,
        message="User created successfully",
    )


@router.get("", summary="List users with pagination and filters")
async def list_users(
    pagination: PaginationParams = Depends(),
    role_id: Optional[int] = Query(None, description="Filter by Role ID"),
    user_status: Optional[str] = Query(None, alias="status", description="Filter by status ('Active' or 'Inactive')"),
    search: Optional[str] = Query(None, description="Search term for name, email, or employee ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns a paginated list of users with optional filtering by role, status, and search query.
    """
    users, total = await UserService.list_users(
        db,
        page=pagination.page,
        limit=pagination.limit,
        role_id=role_id,
        user_status=user_status,
        search=search,
    )
    items = [UserResponse.model_validate(u).model_dump(mode='json') for u in users]
    return create_paginated_response(
        items=items,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        message="Users retrieved successfully",
    )


@router.get("/{user_id}", summary="Get user details by ID")
async def get_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Fetches user details by user ID.
    """
    user = await UserService.get_user_by_id(db, user_id)
    user_response = UserResponse.model_validate(user).model_dump(mode='json')
    return success_response(
        data=user_response,
        message="User details retrieved successfully",
    )


@router.put("/{user_id}", summary="Update user details (Admin only)")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Updates user details and role.
    Only accessible by Admin.
    """
    if user_id == admin_user.id:
        if data.status and data.status.lower() == "inactive":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )
        if data.role_id and data.role_id != admin_user.role_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role.",
            )

    updated_user = await UserService.update_user(db, user_id, data)
    user_response = UserResponse.model_validate(updated_user).model_dump(mode='json')
    return success_response(
        data=user_response,
        message="User details updated successfully",
    )


@router.patch("/{user_id}/status", summary="Toggle user Active/Inactive status (Admin only)")
async def toggle_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Updates user status to 'Active' or 'Inactive' (Soft Delete).
    Only accessible by Admin.
    """
    if user_id == admin_user.id and data.status.lower() == "inactive":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    updated_user = await UserService.toggle_user_status(db, user_id, data.status)
    user_response = UserResponse.model_validate(updated_user).model_dump(mode='json')
    return success_response(
        data=user_response,
        message=f"User status updated to '{updated_user.status}' successfully",
    )
