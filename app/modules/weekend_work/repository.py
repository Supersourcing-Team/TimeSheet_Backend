from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.weekend_work import WeekendWorkRequest


class WeekendWorkRepository:
    """Repository handling database queries for Weekend Work Overtime Requests."""

    @staticmethod
    async def create(db: AsyncSession, request: WeekendWorkRequest) -> WeekendWorkRequest:
        db.add(request)
        await db.commit()
        await db.refresh(request)
        return await WeekendWorkRepository.get_by_id(db, request.id)

    @staticmethod
    async def get_by_id(db: AsyncSession, request_id: int) -> Optional[WeekendWorkRequest]:
        result = await db.execute(
            select(WeekendWorkRequest)
            .options(
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.project),
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.user),
                selectinload(WeekendWorkRequest.approver),
            )
            .filter(WeekendWorkRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_assignment_and_date(
        db: AsyncSession, project_assignment_id: int, work_date: date
    ) -> Optional[WeekendWorkRequest]:
        result = await db.execute(
            select(WeekendWorkRequest).filter(
                WeekendWorkRequest.project_assignment_id == project_assignment_id,
                WeekendWorkRequest.work_date == work_date,
                WeekendWorkRequest.status.in_(["Pending", "Approved"]),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WeekendWorkRequest], int]:
        query = (
            select(WeekendWorkRequest)
            .join(WeekendWorkRequest.project_assignment)
            .options(
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.project),
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.user),
                selectinload(WeekendWorkRequest.approver),
            )
            .filter(ProjectAssignment.user_id == user_id)
        )
        count_query = (
            select(func.count(WeekendWorkRequest.id))
            .join(WeekendWorkRequest.project_assignment)
            .filter(ProjectAssignment.user_id == user_id)
        )

        if status:
            query = query.filter(WeekendWorkRequest.status == status)
            count_query = count_query.filter(WeekendWorkRequest.status == status)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(WeekendWorkRequest.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        requests = list(result.scalars().all())
        return requests, total

    @staticmethod
    async def list_for_pm(
        db: AsyncSession,
        pm_user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WeekendWorkRequest], int]:
        query = (
            select(WeekendWorkRequest)
            .join(WeekendWorkRequest.project_assignment)
            .join(ProjectAssignment.project)
            .options(
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.project),
                selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.user),
                selectinload(WeekendWorkRequest.approver),
            )
            .filter(
                Project.project_manager_id == pm_user_id,
            )
        )
        count_query = (
            select(func.count(WeekendWorkRequest.id))
            .join(WeekendWorkRequest.project_assignment)
            .join(ProjectAssignment.project)
            .filter(
                Project.project_manager_id == pm_user_id,
            )
        )

        if status:
            query = query.filter(WeekendWorkRequest.status == status)
            count_query = count_query.filter(WeekendWorkRequest.status == status)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(WeekendWorkRequest.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        requests = list(result.scalars().all())
        return requests, total

    @staticmethod
    async def list_all(
        db: AsyncSession,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[WeekendWorkRequest], int]:
        query = select(WeekendWorkRequest).options(
            selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.project),
            selectinload(WeekendWorkRequest.project_assignment).selectinload(ProjectAssignment.user),
            selectinload(WeekendWorkRequest.approver),
        )
        count_query = select(func.count(WeekendWorkRequest.id))

        if status:
            query = query.filter(WeekendWorkRequest.status == status)
            count_query = count_query.filter(WeekendWorkRequest.status == status)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(WeekendWorkRequest.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        requests = list(result.scalars().all())
        return requests, total

    @staticmethod
    async def update_status(
        db: AsyncSession,
        request: WeekendWorkRequest,
        status: str,
        approver_id: Optional[int] = None,
    ) -> WeekendWorkRequest:
        request.status = status
        if approver_id is not None:
            request.approved_by = approver_id
            request.approved_at = datetime.now()

        await db.commit()
        await db.refresh(request)
        return await WeekendWorkRepository.get_by_id(db, request.id)

    @staticmethod
    async def delete(db: AsyncSession, request: WeekendWorkRequest) -> None:
        await db.delete(request)
        await db.commit()
