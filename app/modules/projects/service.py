from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schema import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse
from app.modules.clients.repository import ClientRepository
from app.modules.users.repository import UserRepository


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ProjectRepository(db)
        self.client_repo = ClientRepository(db)

    async def _validate_client_and_pm(self, client_id: int = None, pm_id: int = None):
        if client_id is not None:
            client = await self.client_repo.get_by_id(client_id)
            if not client:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid client_id: Client does not exist or is inactive.")
        
        if pm_id is not None:
            pm = await UserRepository.get_by_id(self.db, pm_id)
            if not pm:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_manager_id: User does not exist or is inactive.")
            if not pm.role or pm.role.name != "Project_Manager":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_manager_id: User must have the 'Project_Manager' role.")


    def _to_detail_response(self, project) -> ProjectDetailResponse:
        return ProjectDetailResponse(
            id=project.id,
            client_id=project.client_id,
            project_manager_id=project.project_manager_id,
            project_name=project.project_name,
            description=project.description,
            budget=project.budget,
            start_date=project.start_date,
            end_date=project.end_date,
            status=project.status,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
            client_name=project.client.name if project.client else None,
            project_manager_name=f"{project.project_manager.first_name} {project.project_manager.last_name}".strip() if project.project_manager else None,
            assigned_user_ids=[a.user_id for a in project.assignments] if hasattr(project, "assignments") else [],
            tools=[{"id": t.tool_id, "allocated_hours": t.allocated_hours} for t in project.tool_allocations] if hasattr(project, "tool_allocations") else []
        )

    async def get_project_by_id(self, project_id: int) -> ProjectDetailResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return self._to_detail_response(project)

    async def get_all_projects(self, skip: int = 0, limit: int = 100) -> List[ProjectDetailResponse]:
        projects = await self.repository.get_all(skip=skip, limit=limit)
        return [self._to_detail_response(p) for p in projects]

    async def create_project(self, project_in: ProjectCreate) -> ProjectDetailResponse:
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        project = await self.repository.create(project_in)
        return await self.get_project_by_id(project.id)

    async def update_project(self, project_id: int, project_in: ProjectUpdate) -> ProjectDetailResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        
        updated_project = await self.repository.update(project, project_in)
        return await self.get_project_by_id(updated_project.id)

    async def delete_project(self, project_id: int) -> None:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self.repository.soft_delete(project)
