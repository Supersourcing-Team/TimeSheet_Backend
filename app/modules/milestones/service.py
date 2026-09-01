from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.modules.milestones.repository import MilestoneRepository
from app.modules.milestones.schema import MilestoneCreate, MilestoneUpdate, MilestoneResponse
from app.modules.projects.repository import ProjectRepository
from app.models.user import User

class MilestoneService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = MilestoneRepository(db)
        self.project_repo = ProjectRepository(db)

    async def _check_pm_authorization(self, project_id: int, current_user: User):
        if current_user.role.name != "Project_Manager":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only PMs can manage milestones.")
        
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            
        if project.project_manager_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage milestones for your own projects.")
        
        return project

    async def _validate_weights(self, project_id: int, new_weight: float, exclude_milestone_id: Optional[int] = None):
        existing_milestones = await self.repository.get_by_project_id(project_id)
        total_weight = sum([m.weight_percentage for m in existing_milestones if m.id != exclude_milestone_id])
        if total_weight + new_weight > 100.0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Total milestone weight cannot exceed 100%. Current total is {total_weight}%.")

    async def create_milestone(self, milestone_in: MilestoneCreate, current_user: User) -> MilestoneResponse:
        await self._check_pm_authorization(milestone_in.project_id, current_user)
        await self._validate_weights(milestone_in.project_id, milestone_in.weight_percentage)
        
        milestone = await self.repository.create(milestone_in)
        return MilestoneResponse.model_validate(milestone)

    async def update_milestone(self, milestone_id: int, milestone_in: MilestoneUpdate, current_user: User) -> MilestoneResponse:
        milestone = await self.repository.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found.")
            
        await self._check_pm_authorization(milestone.project_id, current_user)
        
        if milestone_in.weight_percentage is not None:
            await self._validate_weights(milestone.project_id, milestone_in.weight_percentage, exclude_milestone_id=milestone.id)
            
        updated = await self.repository.update(milestone, milestone_in)
        return MilestoneResponse.model_validate(updated)

    async def get_milestones_by_project(self, project_id: int) -> List[MilestoneResponse]:
        milestones = await self.repository.get_by_project_id(project_id)
        return [MilestoneResponse.model_validate(m) for m in milestones]

    async def get_milestone(self, milestone_id: int) -> MilestoneResponse:
        milestone = await self.repository.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found.")
        return MilestoneResponse.model_validate(milestone)

    async def delete_milestone(self, milestone_id: int, current_user: User) -> None:
        milestone = await self.repository.get_by_id(milestone_id)
        if not milestone:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found.")
            
        await self._check_pm_authorization(milestone.project_id, current_user)
        await self.repository.delete(milestone)
