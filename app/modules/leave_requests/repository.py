from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.leave_request import LeaveRequest


class LeaveRequestRepository:
    """Repository handling database queries for Leave Requests."""

    @staticmethod
    async def create(db: AsyncSession, leave_request: LeaveRequest) -> LeaveRequest:
        db.add(leave_request)
        await db.commit()
        await db.refresh(leave_request)
        return await LeaveRequestRepository.get_by_id(db, leave_request.id)

    @staticmethod
    async def get_by_id(db: AsyncSession, request_id: int) -> Optional[LeaveRequest]:
        result = await db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.user),
                selectinload(LeaveRequest.leave_type),
                selectinload(LeaveRequest.manager),
            )
            .filter(LeaveRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[LeaveRequest], int]:
        query = select(LeaveRequest).options(
            selectinload(LeaveRequest.user),
            selectinload(LeaveRequest.leave_type),
            selectinload(LeaveRequest.manager),
        ).filter(LeaveRequest.user_id == user_id)

        count_query = select(func.count(LeaveRequest.id)).filter(LeaveRequest.user_id == user_id)

        if status:
            query = query.filter(LeaveRequest.status == status)
            count_query = count_query.filter(LeaveRequest.status == status)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(LeaveRequest.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        requests = list(result.scalars().all())
        return requests, total

    @staticmethod
    async def list_all(
        db: AsyncSession,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[LeaveRequest], int]:
        query = select(LeaveRequest).options(
            selectinload(LeaveRequest.user),
            selectinload(LeaveRequest.leave_type),
            selectinload(LeaveRequest.manager),
        )
        count_query = select(func.count(LeaveRequest.id))

        if status:
            query = query.filter(LeaveRequest.status == status)
            count_query = count_query.filter(LeaveRequest.status == status)

        if user_id:
            query = query.filter(LeaveRequest.user_id == user_id)
            count_query = count_query.filter(LeaveRequest.user_id == user_id)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        offset = (page - 1) * limit
        query = query.order_by(LeaveRequest.id.desc()).offset(offset).limit(limit)

        result = await db.execute(query)
        requests = list(result.scalars().all())
        return requests, total

    @staticmethod
    async def get_upcoming_team_leaves(
        db: AsyncSession,
        user_ids: Optional[List[int]] = None,
        is_admin: bool = False,
    ) -> List[LeaveRequest]:
        from datetime import date
        query = select(LeaveRequest).options(
            selectinload(LeaveRequest.user),
            selectinload(LeaveRequest.leave_type),
        ).filter(
            LeaveRequest.status.in_(["Approved", "Pending"]),
            LeaveRequest.end_date >= date.today()
        )
        
        if not is_admin and user_ids is not None:
            if not user_ids:
                return []
            query = query.filter(LeaveRequest.user_id.in_(user_ids))
            
        query = query.order_by(LeaveRequest.start_date.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        leave_request: LeaveRequest,
        status: str,
        manager_id: Optional[int] = None,
        rejection_reason: Optional[str] = None,
    ) -> LeaveRequest:
        leave_request.status = status
        if manager_id is not None:
            leave_request.managers_user_id = manager_id
        if rejection_reason is not None:
            leave_request.rejection_reason = rejection_reason

        await db.commit()
        await db.refresh(leave_request)
        return await LeaveRequestRepository.get_by_id(db, leave_request.id)

    @staticmethod
    async def delete(db: AsyncSession, leave_request: LeaveRequest) -> None:
        await db.delete(leave_request)
        await db.commit()

    @staticmethod
    async def get_approved_leaves_for_date(
        db: AsyncSession,
        user_id: int,
        leave_date: "date",
    ) -> List[LeaveRequest]:
        """Return all Approved/Pending leave records for a user that cover a specific date."""
        from datetime import date as date_type
        result = await db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
            )
            .filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.start_date <= leave_date,
                LeaveRequest.end_date >= leave_date,
                LeaveRequest.status.in_(["Approved", "Pending"]),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_approved_leaves_for_range(
        db: AsyncSession,
        user_id: int,
        start_date: "date",
        end_date: "date",
    ) -> List[LeaveRequest]:
        """Return all Approved/Pending leave records for a user that overlap a date range."""
        result = await db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
            )
            .filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
                LeaveRequest.status.in_(["Approved", "Pending"]),
            )
        )
        return list(result.scalars().all())


