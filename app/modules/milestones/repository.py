from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.milestones.model import Milestone
from app.modules.milestones.schema import MilestoneCreate, MilestoneUpdate

class MilestoneRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, milestone_id: int) -> Optional[Milestone]:
        result = await self.db.execute(select(Milestone).where(Milestone.id == milestone_id))
        return result.scalars().first()

    async def get_by_project_id(self, project_id: int) -> List[Milestone]:
        result = await self.db.execute(select(Milestone).where(Milestone.project_id == project_id))
        return list(result.scalars().all())

    async def create(self, milestone_in: MilestoneCreate) -> Milestone:
        milestone = Milestone(**milestone_in.model_dump())
        self.db.add(milestone)
        await self.db.commit()
        await self.db.refresh(milestone)
        return milestone

    async def update(self, milestone: Milestone, milestone_in: MilestoneUpdate) -> Milestone:
        update_data = milestone_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(milestone, field, value)
        
        # Auto-set actual_achievement_date if status changes to achieved
        if update_data.get("status") == "achieved" and milestone.actual_achievement_date is None:
            from datetime import datetime, timezone
            milestone.actual_achievement_date = datetime.now(timezone.utc)
        elif update_data.get("status") in ["planned", "in_progress"]:
            milestone.actual_achievement_date = None

        await self.db.commit()
        await self.db.refresh(milestone)
        return milestone

    async def delete(self, milestone: Milestone) -> None:
        await self.db.delete(milestone)
        await self.db.commit()
