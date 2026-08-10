from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_balance import LeaveBalance


class LeaveBalanceRepository:
    @staticmethod
    async def get_by_user_and_year(
        db: AsyncSession, user_id: int, year: int
    ) -> List[LeaveBalance]:
        query = (
            select(LeaveBalance)
            .where(LeaveBalance.user_id == user_id, LeaveBalance.year == year)
            .order_by(LeaveBalance.leave_type_id.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_specific_balance(
        db: AsyncSession, user_id: int, leave_type_id: int, year: int
    ) -> Optional[LeaveBalance]:
        query = select(LeaveBalance).where(
            LeaveBalance.user_id == user_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, balance_id: int) -> Optional[LeaveBalance]:
        query = select(LeaveBalance).where(LeaveBalance.id == balance_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession, user_id: int, leave_type_id: int, year: int, allocated_days: float
    ) -> LeaveBalance:
        balance = LeaveBalance(
            user_id=user_id,
            leave_type_id=leave_type_id,
            year=year,
            allocated_days=allocated_days,
            used_days=0.0,
        )
        db.add(balance)
        await db.commit()
        await db.refresh(balance)
        return balance

    @staticmethod
    async def update(db: AsyncSession, balance: LeaveBalance, **data) -> LeaveBalance:
        for key, value in data.items():
            if value is not None:
                setattr(balance, key, value)
        await db.commit()
        await db.refresh(balance)
        return balance
