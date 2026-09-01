from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schema import ProjectCreate, ProjectUpdate, ProjectResponse
from app.modules.clients.repository import ClientRepository
from app.modules.users.repository import UserRepository
from app.models.user import User


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

    @staticmethod
    def _is_pm(user: Optional[User]) -> bool:
        if not user or not user.role:
            return False
        return user.role.name == "Project_Manager"

    async def get_project_by_id(self, project_id: int, current_user: Optional[User] = None) -> ProjectResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        financials = await self.compute_financials_for_projects(self.db, [project], current_user=current_user)
        return financials[0]

    async def get_all_projects(self, skip: int = 0, limit: int = 100, current_user: Optional[User] = None) -> List[ProjectResponse]:
        projects = await self.repository.get_all(skip=skip, limit=limit)
        return await self.compute_financials_for_projects(self.db, projects, current_user=current_user)

    @staticmethod
    async def compute_financials_for_projects(db: AsyncSession, projects: list, current_user: Optional[User] = None) -> List[ProjectResponse]:
        if not projects:
            return []

        from sqlalchemy import select, func
        from app.models.project_assignment import ProjectAssignment
        from app.models.timesheet import Timesheet
        from app.models.milestone import Milestone
        from app.models.milestone_assignment import MilestoneAssignment
        from app.modules.milestones.schema import MilestoneResponse

        project_ids = [p.id for p in projects]

        try:
            stmt = (
                select(
                    ProjectAssignment.project_id,
                    func.coalesce(func.sum(Timesheet.billable_hours + Timesheet.non_billable_hours), 0.0).label("logged_hours")
                )
                .join(Timesheet, Timesheet.project_assignment_id == ProjectAssignment.id)
                .where(ProjectAssignment.project_id.in_(project_ids))
                .group_by(ProjectAssignment.project_id)
            )
            res = await db.execute(stmt)
            hours_map = {row.project_id: float(row.logged_hours) for row in res.all()}
        except Exception:
            hours_map = {}

        from sqlalchemy.orm import selectinload
        try:
            m_stmt = select(Milestone).options(
                selectinload(Milestone.assignments).selectinload(MilestoneAssignment.user)
            ).where(Milestone.project_id.in_(project_ids))
            m_res = await db.execute(m_stmt)
            all_milestones = m_res.scalars().all()
            milestone_map = {}
            for m in all_milestones:
                milestone_map.setdefault(m.project_id, []).append(m)
        except Exception:
            milestone_map = {}

        is_ac_manager = current_user and current_user.role and current_user.role.name == "Account_Manager"
        is_admin = current_user and current_user.role and current_user.role.name == "Admin"
        
        # User explicitly requested: "only AC manager will tkae care of finacial thigns"
        can_view_budget = is_ac_manager
        results = []
        for p in projects:
            project_milestones = milestone_map.get(p.id, [])
            
            # Calculate project budget from milestones (if the project itself doesn't have an override)
            calculated_budget = sum([float(m.budget or 0.0) for m in project_milestones])
            budget = float(p.budget or calculated_budget)

            logged_hours = hours_map.get(p.id, 0.0)
            
            completion_percentage = sum([m.weight_percentage for m in project_milestones if m.status == "achieved"])
            
            # Milestone Duration * Employee Daily Cost
            cost = 0.0
            for m in project_milestones:
                if m.start_date and m.expected_completion_date:
                    duration_days = (m.expected_completion_date - m.start_date).days
                    if duration_days > 0:
                        for assignment in m.assignments:
                            if assignment.is_active and assignment.user:
                                cost += (duration_days * assignment.user.daily_cost)
            
            revenue = budget * (completion_percentage / 100.0)
            profit = revenue - cost

            resp = ProjectResponse.model_validate(p)
            resp.milestones = [MilestoneResponse.model_validate(m) for m in project_milestones]
            resp.completion_percentage = round(completion_percentage, 2)
            resp.logged_hours = round(logged_hours, 2)
            resp.cost = round(cost, 2)
            resp.revenue = round(revenue, 2)
            resp.profit = round(profit, 2)

            # Restrict budget visibility (Only AC Manager can see budget/financials)
            if not can_view_budget:
                resp.budget = None
                resp.cost = 0.0
                resp.revenue = 0.0
                resp.profit = 0.0

            results.append(resp)

        return results

    async def create_project(self, project_in: ProjectCreate, current_user: Optional[User] = None) -> ProjectResponse:
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        
        # Only AC Manager can enter or modify project budget
        is_ac_manager = current_user and current_user.role and current_user.role.name == "Account_Manager"
        if not is_ac_manager:
            project_in.budget = None

        project = await self.repository.create(project_in)
        
        from app.modules.project_assignments.schema import ProjectAssignmentCreate
        from app.modules.project_assignments.repository import ProjectAssignmentRepository
        
        assignment_repo = ProjectAssignmentRepository(self.db)
        existing = await assignment_repo.get_any_assignment(project.id, project.project_manager_id)
        if not existing:
            await assignment_repo.create(ProjectAssignmentCreate(
                project_id=project.id,
                user_id=project.project_manager_id
            ))

        fetched = await self.repository.get_by_id(project.id)
        target_project = fetched if fetched else project
        financials = await self.compute_financials_for_projects(self.db, [target_project], current_user=current_user)
        return financials[0]

    async def update_project(self, project_id: int, project_in: ProjectUpdate, current_user: Optional[User] = None) -> ProjectResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        
        # Only AC Manager can modify project budget
        is_ac_manager = current_user and current_user.role and current_user.role.name == "Account_Manager"
        if not is_ac_manager:
            project_in.budget = None

        updated_project = await self.repository.update(project, project_in)
        financials = await self.compute_financials_for_projects(self.db, [updated_project], current_user=current_user)
        return financials[0]

    async def delete_project(self, project_id: int) -> None:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self.repository.soft_delete(project)
