from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.model import Department
from app.modules.departments.schema import DepartmentCreate, DepartmentUpdate
from app.modules.users.model import User


class DepartmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, dept_id: int) -> Optional[Department]:
        result = await self.db.execute(
            select(Department).where(Department.id == dept_id)
        )
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Optional[Department]:
        result = await self.db.execute(
            select(Department).where(func.lower(Department.name) == func.lower(name.strip()))
        )
        return result.scalars().first()

    async def get_by_code(self, code: str) -> Optional[Department]:
        result = await self.db.execute(
            select(Department).where(func.lower(Department.code) == func.lower(code.strip()))
        )
        return result.scalars().first()

    async def get_all_with_counts(self, active_only: bool = True) -> List[Tuple[Department, int]]:
        query = (
            select(Department, func.count(User.id).label("employee_count"))
            .outerjoin(User, (User.department_id == Department.id) & (User.status != "Inactive"))
            .group_by(Department.id)
            .order_by(Department.name.asc())
        )
        if active_only:
            query = query.where(Department.is_active == True) # noqa: E712

        result = await self.db.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def count_assigned_users(self, dept_id: int) -> int:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.department_id == dept_id, User.status != "Inactive")
        )
        return result.scalar() or 0

    async def create(self, dept_in: DepartmentCreate) -> Department:
        dept = Department(**dept_in.model_dump())
        self.db.add(dept)
        await self.db.commit()
        await self.db.refresh(dept)
        return dept

    async def update(self, dept: Department, dept_in: DepartmentUpdate) -> Department:
        update_data = dept_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(dept, field, value)
        await self.db.commit()
        await self.db.refresh(dept)
        return dept

    async def delete(self, dept: Department) -> None:
        await self.db.delete(dept)
        await self.db.commit()
