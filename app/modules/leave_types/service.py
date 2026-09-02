from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leave_types.model import LeaveType
from app.modules.leave_types.repository import LeaveTypeRepository
from app.modules.leave_types.schema import LeaveTypeCreate, LeaveTypeUpdate


class LeaveTypeService:
    @staticmethod
    async def get_leave_types(db: AsyncSession, active_only: bool = True) -> List[LeaveType]:
        return await LeaveTypeRepository.get_all(db, active_only=active_only)

    @staticmethod
    async def get_leave_type(db: AsyncSession, leave_type_id: int) -> LeaveType:
        leave_type = await LeaveTypeRepository.get_by_id(db, leave_type_id)
        if not leave_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave type with ID {leave_type_id} not found",
            )
        return leave_type

    @staticmethod
    async def create_leave_type(db: AsyncSession, data: LeaveTypeCreate) -> LeaveType:
        existing = await LeaveTypeRepository.get_by_name(db, data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave type with name '{data.name}' already exists",
            )
        existing_code = await LeaveTypeRepository.get_by_code(db, data.code)
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave type with code '{data.code}' already exists",
            )
        return await LeaveTypeRepository.create(db, **data.model_dump())

    @staticmethod
    async def update_leave_type(
        db: AsyncSession, leave_type_id: int, data: LeaveTypeUpdate
    ) -> LeaveType:
        leave_type = await LeaveTypeService.get_leave_type(db, leave_type_id)
        if data.name and data.name != leave_type.name:
            existing = await LeaveTypeRepository.get_by_name(db, data.name)
            if existing and existing.id != leave_type_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Leave type with name '{data.name}' already exists",
                )
        if data.code and data.code != leave_type.code:
            existing_code = await LeaveTypeRepository.get_by_code(db, data.code)
            if existing_code and existing_code.id != leave_type_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Leave type with code '{data.code}' already exists",
                )
        return await LeaveTypeRepository.update(db, leave_type, **data.model_dump(exclude_unset=True))

    @staticmethod
    async def delete_leave_type(db: AsyncSession, leave_type_id: int) -> LeaveType:
        leave_type = await LeaveTypeService.get_leave_type(db, leave_type_id)
        return await LeaveTypeRepository.delete(db, leave_type)
