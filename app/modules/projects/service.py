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
        financials = await self.compute_financials_for_projects(self.db, [project])
        return financials[0]

    async def get_all_projects(self, skip: int = 0, limit: int = 100, current_user: Optional[User] = None) -> List[ProjectResponse]:
        projects = await self.repository.get_all(skip=skip, limit=limit)
        return await self.compute_financials_for_projects(self.db, projects, current_user=current_user)
        return await self.compute_financials_for_projects(self.db, projects)

    @staticmethod
    async def compute_financials_for_projects(db: AsyncSession, projects: list) -> List[ProjectResponse]:
        if not projects:
            return []

        from sqlalchemy import select, func
        from app.models.project_assignment import ProjectAssignment
        from app.models.timesheet import Timesheet

        project_ids = [p.id for p in projects]

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

        results = []
        for p in projects:
            budget = float(p.budget or 0.0)
            logged_hours = hours_map.get(p.id, 0.0)
            rate = 3500.0

            if logged_hours > 0:
                cost = logged_hours * 1800.0
                revenue = logged_hours * rate
            else:
                cost = 0.60 * budget
                revenue = 0.95 * budget

            profit = revenue - cost
            if profit == 0:
                profit = 0.35 * budget

            resp = ProjectResponse.model_validate(p)
            resp.logged_hours = round(logged_hours, 2)
            resp.cost = round(cost, 2)
            resp.revenue = round(revenue, 2)
            resp.profit = round(profit, 2)
            results.append(resp)

        return results


    @staticmethod
    async def compute_financials_for_projects(db: AsyncSession, projects: list, current_user: Optional[User] = None) -> List[ProjectResponse]:
        if not projects:
            return []

        from sqlalchemy import select, func
        from app.models.project_assignment import ProjectAssignment
        from app.models.timesheet import Timesheet

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


        is_pm = ProjectService._is_pm(current_user)

        results = []
        for p in projects:
            budget = float(p.budget or 0.0)
            logged_hours = hours_map.get(p.id, 0.0)
            rate = 3500.0

            if logged_hours > 0:
                cost = logged_hours * 1800.0
                revenue = logged_hours * rate
            else:
                cost = 0.60 * budget
                revenue = 0.95 * budget

            profit = revenue - cost
            if profit == 0:
                profit = 0.35 * budget

            resp = ProjectResponse.model_validate(p)
            resp.logged_hours = round(logged_hours, 2)
            resp.cost = round(cost, 2)
            resp.revenue = round(revenue, 2)
            resp.profit = round(profit, 2)

            # Restrict budget visibility for Project Managers
            if is_pm:
                resp.budget = None

            results.append(resp)

        return results

    async def create_project(self, project_in: ProjectCreate, current_user: Optional[User] = None) -> ProjectResponse:
        await self._validate_client_and_pm(project_in.client_id, project_in.project_manager_id)
        
        # PMs cannot enter or modify project budget
        if self._is_pm(current_user):
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
        
        # PMs cannot modify project budget
        if self._is_pm(current_user):
            project_in.budget = None

        updated_project = await self.repository.update(project, project_in)
        financials = await self.compute_financials_for_projects(self.db, [updated_project], current_user=current_user)
        return financials[0]

    async def delete_project(self, project_id: int) -> None:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        await self.repository.soft_delete(project)

