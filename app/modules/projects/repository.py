from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.projects.model import Project, ProjectDocument
from app.modules.projects.schema import ProjectCreate, ProjectUpdate

from app.modules.project_assignments.model import ProjectAssignment
from app.modules.tool_allocations.model import ToolAllocation
from app.modules.milestones.model import Milestone

class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        result = await self.db.execute(
            select(Project)
            .options(
                selectinload(Project.client), 
                selectinload(Project.project_manager),
                selectinload(Project.assignments).selectinload(ProjectAssignment.user),
                selectinload(Project.milestones).selectinload(Milestone.tool_allocations).selectinload(ToolAllocation.tool),
                selectinload(Project.documents)
            )
            .where(Project.id == project_id)
        )
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Project]:
        result = await self.db.execute(
            select(Project)
            .options(
                selectinload(Project.client), 
                selectinload(Project.project_manager),
                selectinload(Project.assignments).selectinload(ProjectAssignment.user),
                selectinload(Project.milestones).selectinload(Milestone.tool_allocations).selectinload(ToolAllocation.tool),
                selectinload(Project.documents)
            )
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, project_in: ProjectCreate) -> Project:
        project = Project(**project_in.model_dump())
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def update(self, project: Project, project_in: ProjectUpdate) -> Project:
        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def soft_delete(self, project: Project) -> Project:
        project.is_active = False
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def add_document(self, document: ProjectDocument) -> ProjectDocument:
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def get_document_by_id(self, document_id: int) -> Optional[ProjectDocument]:
        result = await self.db.execute(
            select(ProjectDocument).where(ProjectDocument.id == document_id)
        )
        return result.scalars().first()

    async def delete_document(self, document: ProjectDocument) -> None:
        await self.db.delete(document)
        await self.db.commit()
