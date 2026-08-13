from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.timesheet import Timesheet


class TimesheetRepository:
    """Repository handling database queries for Timesheets."""

    @staticmethod
    async def create(db: AsyncSession, timesheet: Timesheet) -> Timesheet:
        db.add(timesheet)
        await db.commit()
        await db.refresh(timesheet)
        return await TimesheetRepository.get_by_id(db, timesheet.id)

    @staticmethod
    async def get_by_id(db: AsyncSession, timesheet_id: int) -> Optional[Timesheet]:
        result = await db.execute(
            select(Timesheet)
            .options(selectinload(Timesheet.project_assignment))
            .filter(Timesheet.id == timesheet_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_daily_total_hours(
        db: AsyncSession,
        user_id: int,
        timesheet_date: date,
        exclude_id: Optional[int] = None,
    ) -> float:
        query = select(
            func.coalesce(func.sum(Timesheet.billable_hours + Timesheet.non_billable_hours), 0.0)
        ).filter(
            Timesheet.user_id == user_id,
            Timesheet.timesheet_date == timesheet_date,
        )
        if exclude_id is not None:
            query = query.filter(Timesheet.id != exclude_id)

        res = await db.execute(query)
        return float(res.scalar_one())

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_assignment_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Timesheet], int]:
        query = select(Timesheet).options(
            selectinload(Timesheet.project_assignment)
        ).filter(Timesheet.user_id == user_id)

        count_query = select(func.count(Timesheet.id)).filter(Timesheet.user_id == user_id)

        if start_date:
            query = query.filter(Timesheet.timesheet_date >= start_date)
            count_query = count_query.filter(Timesheet.timesheet_date >= start_date)

        if end_date:
            query = query.filter(Timesheet.timesheet_date <= end_date)
            count_query = count_query.filter(Timesheet.timesheet_date <= end_date)

        if project_assignment_id:
            query = query.filter(Timesheet.project_assignment_id == project_assignment_id)
            count_query = count_query.filter(Timesheet.project_assignment_id == project_assignment_id)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(Timesheet.timesheet_date.desc(), Timesheet.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        entries = list(result.scalars().all())
        return entries, total

    @staticmethod
    async def get_by_user_project_date(
        db: AsyncSession,
        user_id: int,
        project_assignment_id: int,
        timesheet_date: date,
    ) -> Optional[Timesheet]:
        query = select(Timesheet).filter(
            Timesheet.user_id == user_id,
            Timesheet.project_assignment_id == project_assignment_id,
            Timesheet.timesheet_date == timesheet_date,
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_entries_in_range(
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> List[Timesheet]:
        query = (
            select(Timesheet)
            .options(selectinload(Timesheet.project_assignment))
            .filter(
                Timesheet.user_id == user_id,
                Timesheet.timesheet_date >= start_date,
                Timesheet.timesheet_date <= end_date,
            )
            .order_by(Timesheet.timesheet_date.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        timesheet: Timesheet,
        update_data: dict,
    ) -> Timesheet:
        for field, value in update_data.items():
            if value is not None:
                setattr(timesheet, field, value)
        await db.commit()
        await db.refresh(timesheet)
        return await TimesheetRepository.get_by_id(db, timesheet.id)

    @staticmethod
    async def delete(db: AsyncSession, timesheet: Timesheet) -> None:
        await db.delete(timesheet)
        await db.commit()
