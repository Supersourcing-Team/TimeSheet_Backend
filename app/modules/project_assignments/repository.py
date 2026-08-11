from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project_assignment import ProjectAssignment
from app.modules.project_assignments.schema import ProjectAssignmentCreate


class ProjectAssignmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, assignment_id: int) -> Optional[ProjectAssignment]:
        result = await self.db.execute(
            select(ProjectAssignment)
            .where(ProjectAssignment.id == assignment_id, ProjectAssignment.is_active == True)
        )
        return result.scalars().first()

    async def get_assignment(self, project_id: int, user_id: int) -> Optional[ProjectAssignment]:
        result = await self.db.execute(
            select(ProjectAssignment)
            .where(
                and_(
                    ProjectAssignment.project_id == project_id,
                    ProjectAssignment.user_id == user_id,
                    ProjectAssignment.is_active == True
                )
            )
        )
        return result.scalars().first()

    async def get_by_project(self, project_id: int, skip: int = 0, limit: int = 100) -> List[ProjectAssignment]:
        result = await self.db.execute(
            select(ProjectAssignment)
            .where(ProjectAssignment.project_id == project_id, ProjectAssignment.is_active == True)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[ProjectAssignment]:
        result = await self.db.execute(
            select(ProjectAssignment)
            .where(ProjectAssignment.user_id == user_id, ProjectAssignment.is_active == True)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, assignment_in: ProjectAssignmentCreate) -> ProjectAssignment:
        assignment = ProjectAssignment(**assignment_in.model_dump())
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def soft_delete(self, assignment: ProjectAssignment) -> ProjectAssignment:
        assignment.is_active = False
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment
