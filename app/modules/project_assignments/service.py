from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.modules.project_assignments.repository import ProjectAssignmentRepository
from app.modules.project_assignments.schema import ProjectAssignmentCreate, ProjectAssignmentResponse
from app.modules.projects.repository import ProjectRepository
from app.modules.users.repository import UserRepository


class ProjectAssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ProjectAssignmentRepository(db)
        self.project_repo = ProjectRepository(db)

    async def assign_user_to_project(self, assignment_in: ProjectAssignmentCreate) -> ProjectAssignmentResponse:
        # Check if project exists and is active
        project = await self.project_repo.get_by_id(assignment_in.project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        # Check if user exists and is active
        user = await UserRepository.get_by_id(self.db, assignment_in.user_id)
        if not user or user.status != "Active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or inactive")

        # Check if already assigned
        existing_assignment = await self.repository.get_assignment(assignment_in.project_id, assignment_in.user_id)
        if existing_assignment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already assigned to this project")

        assignment = await self.repository.create(assignment_in)
        return ProjectAssignmentResponse.model_validate(assignment)

    async def get_project_assignments(self, project_id: int, skip: int = 0, limit: int = 100) -> List[ProjectAssignmentResponse]:
        # Check if project exists
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            
        assignments = await self.repository.get_by_project(project_id, skip=skip, limit=limit)
        return [ProjectAssignmentResponse.model_validate(a) for a in assignments]

    async def get_user_assignments(self, user_id: int, skip: int = 0, limit: int = 100) -> List[ProjectAssignmentResponse]:
        # Check if user exists
        user = await UserRepository.get_by_id(self.db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        assignments = await self.repository.get_by_user(user_id, skip=skip, limit=limit)
        return [ProjectAssignmentResponse.model_validate(a) for a in assignments]

    async def remove_assignment(self, assignment_id: int) -> None:
        assignment = await self.repository.get_by_id(assignment_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project assignment not found")
        
        await self.repository.soft_delete(assignment)

    async def remove_assignment_by_project_user(self, project_id: int, user_id: int) -> None:
        assignment = await self.repository.get_assignment(project_id, user_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project assignment not found")
        
        await self.repository.soft_delete(assignment)
