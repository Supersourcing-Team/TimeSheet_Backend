from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leave_balances.model import LeaveBalance
from app.modules.leave_balances.repository import LeaveBalanceRepository
from app.modules.leave_balances.schema import LeaveBalanceCreate, LeaveBalanceResponse, LeaveBalanceUpdate
from app.modules.leave_types.repository import LeaveTypeRepository


class LeaveBalanceService:
    @staticmethod
    def _format_balance_response(b: LeaveBalance, leave_type_name: Optional[str] = None) -> LeaveBalanceResponse:
        remaining = max(0.0, b.allocated_days - b.used_days)
        return LeaveBalanceResponse(
            id=b.id,
            user_id=b.user_id,
            leave_type_id=b.leave_type_id,
            leave_type_name=leave_type_name,
            year=b.year,
            allocated_days=b.allocated_days,
            used_days=b.used_days,
            remaining_days=remaining,
            updated_at=b.updated_at or datetime.now(),
        )

    @staticmethod
    async def get_user_balances(
        db: AsyncSession, user_id: int, year: Optional[int] = None
    ) -> List[LeaveBalanceResponse]:
        target_year = year or datetime.now().year
        active_leave_types = await LeaveTypeRepository.get_all(db, active_only=True)
        custom_balances = await LeaveBalanceRepository.get_by_user_and_year(db, user_id, target_year)
        balance_map = {b.leave_type_id: b for b in custom_balances}

        responses = []
        for lt in active_leave_types:
            if lt.id in balance_map:
                b = balance_map[lt.id]
                responses.append(LeaveBalanceService._format_balance_response(b, leave_type_name=lt.name))
            else:
                # Direct reference from Admin configured LeaveType policy (days_per_year)
                allocated = float(lt.days_per_year) if lt.days_per_year is not None else 0.0

                responses.append(
                    LeaveBalanceResponse(
                        id=lt.id,
                        user_id=user_id,
                        leave_type_id=lt.id,
                        leave_type_name=lt.name,
                        year=target_year,
                        allocated_days=allocated,
                        used_days=0.0,
                        remaining_days=allocated,
                        updated_at=datetime.now(),
                    )
                )


        return responses


    @staticmethod
    async def allocate_balance(
        db: AsyncSession, data: LeaveBalanceCreate
    ) -> LeaveBalanceResponse:
        leave_type = await LeaveTypeRepository.get_by_id(db, data.leave_type_id)
        if not leave_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave type with ID {data.leave_type_id} not found",
            )
        existing = await LeaveBalanceRepository.get_specific_balance(
            db, user_id=data.user_id, leave_type_id=data.leave_type_id, year=data.year
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave balance allocation already exists for user {data.user_id}, leave type {data.leave_type_id}, year {data.year}",
            )
        balance = await LeaveBalanceRepository.create(
            db,
            user_id=data.user_id,
            leave_type_id=data.leave_type_id,
            year=data.year,
            allocated_days=data.allocated_days,
        )
        return LeaveBalanceService._format_balance_response(balance)

    @staticmethod
    async def update_balance(
        db: AsyncSession, balance_id: int, data: LeaveBalanceUpdate
    ) -> LeaveBalanceResponse:
        balance = await LeaveBalanceRepository.get_by_id(db, balance_id)
        if not balance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave balance with ID {balance_id} not found",
            )
        updated = await LeaveBalanceRepository.update(db, balance, **data.model_dump(exclude_unset=True))
        return LeaveBalanceService._format_balance_response(updated)
