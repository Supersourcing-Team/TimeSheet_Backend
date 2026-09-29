from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.keka.model import KekaEmployeeMapping


class KekaEmployeeMappingRepository:
    """Repository handling database operations for KekaEmployeeMapping."""

    @staticmethod
    async def get_by_keka_employee_id(
        db: AsyncSession, keka_employee_id: str
    ) -> Optional[KekaEmployeeMapping]:
        """Fetch mapping by unique Keka employee UUID."""
        query = (
            select(KekaEmployeeMapping)
            .options(selectinload(KekaEmployeeMapping.user))
            .where(KekaEmployeeMapping.keka_employee_id == keka_employee_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_local_user_id(
        db: AsyncSession, local_user_id: int
    ) -> Optional[KekaEmployeeMapping]:
        """Fetch mapping by unique local user ID."""
        query = (
            select(KekaEmployeeMapping)
            .options(selectinload(KekaEmployeeMapping.user))
            .where(KekaEmployeeMapping.local_user_id == local_user_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_mapping(
        db: AsyncSession,
        keka_employee_id: str,
        local_user_id: int,
        keka_employee_number: Optional[str] = None,
        sync_status: str = "active",
        last_synced_at: Optional[datetime] = None,
    ) -> KekaEmployeeMapping:
        """Create and persist a new Keka employee mapping."""
        mapping = KekaEmployeeMapping(
            keka_employee_id=keka_employee_id,
            local_user_id=local_user_id,
            keka_employee_number=keka_employee_number,
            sync_status=sync_status,
            last_synced_at=last_synced_at,
        )
        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)
        return await KekaEmployeeMappingRepository.get_by_keka_employee_id(
            db, keka_employee_id
        ) or mapping

    @staticmethod
    async def update_mapping(
        db: AsyncSession, mapping: KekaEmployeeMapping, **kwargs: Any
    ) -> KekaEmployeeMapping:
        """Update fields on an existing mapping."""
        for key, value in kwargs.items():
            if hasattr(mapping, key) and value is not None:
                setattr(mapping, key, value)
        await db.commit()
        await db.refresh(mapping)
        return mapping

    @staticmethod
    async def list_mappings(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Tuple[List[KekaEmployeeMapping], int]:
        """List mappings with pagination and total count."""
        count_query = select(func.count(KekaEmployeeMapping.id))
        total_count = (await db.execute(count_query)).scalar() or 0

        query = (
            select(KekaEmployeeMapping)
            .options(selectinload(KekaEmployeeMapping.user))
            .order_by(KekaEmployeeMapping.id.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        mappings = list(result.scalars().all())

        return mappings, total_count

    @staticmethod
    async def delete_mapping(
        db: AsyncSession, mapping: KekaEmployeeMapping
    ) -> bool:
        """Hard delete an employee mapping from the database."""
        await db.delete(mapping)
        await db.commit()
        return True
