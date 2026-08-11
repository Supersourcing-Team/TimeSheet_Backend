from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schema import ProjectCreate, ProjectUpdate, ProjectResponse
from app.modules.clients.repository import ClientRepository
from app.modules.users.repository import UserRepository


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.repository = ProjectRepository(db)
        self.client_repo = ClientRepository(db)
        self.user_repo = UserRepository(db)

    async def _validate_client_and_pm(self, client_id: int = None, pm_id: int = None):
        if client_id is not None:
            client = await self.client_repo.get_by_id(client_id)
            if not client:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid client_id: Client does not exist or is inactive.")
        
        if pm_id is not None:
            pm = await self.user_repo.get_by_id(pm_id)
            if not pm:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_manager_id: User does not exist or is inactive.")
            if not pm.role or pm.role.name != "Project_Manager":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_manager_id: User must have the 'Project_Manager' role.")

    async def get_project_by_id(self, project_id: int) -> ProjectResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return ProjectResponse.model_validate(project)

    async def get_all_projects(self, skip: int = 0, limit: int = 100) -> List[ProjectResponse]:
        projects = await self.repository.get_all(skip=skip, limit=limit)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def create_project(self, project_in: ProjectCreate) -> ProjectResponse:
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        project = await self.repository.create(project_in)
        return ProjectResponse.model_validate(project)

    async def update_project(self, project_id: int, project_in: ProjectUpdate) -> ProjectResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        
        updated_project = await self.repository.update(project, project_in)
        return ProjectResponse.model_validate(updated_project)

    async def delete_project(self, project_id: int) -> None:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self.repository.soft_delete(project)
