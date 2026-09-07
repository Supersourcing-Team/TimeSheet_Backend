from typing import List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, UploadFile, status
from app.modules.projects.model import ProjectDocument
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schema import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDocumentResponse
from app.modules.clients.repository import ClientRepository
from app.modules.users.repository import UserRepository
from app.modules.users.model import User
from app.common.file_handler import save_upload_file, delete_file, ALLOWED_DOCUMENT_EXTENSIONS


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

        from app.common.financial_engine import FinancialEngine
        from app.modules.milestones.model import Milestone
        from app.modules.milestones.assignment_model import MilestoneAssignment
        from app.modules.milestones.schema import MilestoneResponse
        from datetime import date
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        engine = FinancialEngine(db)
        project_ids = [p.id for p in projects]

        try:
            m_stmt = select(Milestone).options(
                selectinload(Milestone.assignments).selectinload(MilestoneAssignment.user)
            ).where(Milestone.project_id.in_(project_ids))
            m_res = await db.execute(m_stmt)
            all_milestones = m_res.scalars().unique().all()
            milestone_map = {}
            for m in all_milestones:
                milestone_map.setdefault(m.project_id, []).append(m)
        except Exception:
            milestone_map = {}

        is_ac_manager = current_user and current_user.role and current_user.role.name == "Account_Manager"
        is_admin = current_user and current_user.role and current_user.role.name.lower() == "admin"
        can_view_budget = is_ac_manager or is_admin
        
        today = date.today()
        results = []

        for p in projects:
            if not hasattr(p, 'milestones'):
                p.milestones = milestone_map.get(p.id, [])
            else:
                p.milestones = milestone_map.get(p.id, [])

            total_weight = sum([float(m.weight_percentage) for m in p.milestones])
            valid_weight = abs(total_weight - 100.0) < 0.001

            fin_data = await engine.compute_project_financials(p)
            
            m_responses = []
            for m in p.milestones:
                m_fin = fin_data["milestone_financials"].get(m.id, {})
                
                delay_days = 0
                if m.actual_start_date and m.expected_completion_date:
                    end_date_to_use = m.actual_achievement_date.date() if m.actual_achievement_date else today
                    delay_days = max(0, (end_date_to_use - m.expected_completion_date).days)
                
                planned_duration = 0
                if m.start_date and m.expected_completion_date:
                    planned_duration = max(0, (m.expected_completion_date - m.start_date).days)
                
                actual_duration = 0
                start_date_to_use = m.actual_start_date or m.start_date or p.start_date
                if start_date_to_use:
                    end_date_to_use = m.actual_achievement_date.date() if m.actual_achievement_date else today
                    actual_duration = max(1, (end_date_to_use - start_date_to_use).days)

                m_resp = MilestoneResponse.model_validate(m)
                m_resp.completion_percentage = m.completion_percentage or 0.0
                if str(m.status).lower() == "achieved":
                    m_resp.completion_percentage = 100.0

                m_resp.planned_value = m_fin.get("pv", 0.0)
                m_resp.earned_value = m_fin.get("ev", 0.0)
                m_resp.actual_cost = m_fin.get("ac", 0.0)
                m_resp.forecast_cost = m_fin.get("eac", 0.0)
                m_resp.cost_variance = m_fin.get("cv", 0.0)
                m_resp.cpi = m_fin.get("cpi", 0.0)
                m_resp.delay_days = delay_days
                m_resp.planned_duration_days = planned_duration
                m_resp.actual_duration_days = actual_duration
                m_responses.append(m_resp)

            health = "GREEN"
            fin_status = "FORECAST_WITHIN_BUDGET"
            
            total_delay = sum([m.delay_days or 0 for m in m_responses])
            project_budget = fin_data["budget"]
            project_eac = fin_data["eac"]
            project_cpi = fin_data["cpi"]
            project_ev = fin_data["ev"]
            project_ac = fin_data["ac"]
            
            if project_eac > project_budget:
                fin_status = "FORECAST_OVER_BUDGET"
            
            if total_delay > 10 or project_cpi < 0.85 or project_eac > project_budget:
                health = "RED"
            elif total_delay > 5 or project_cpi < 1.0 or (project_budget > 0 and (project_eac / project_budget) > 0.9):
                health = "AMBER"

            if not valid_weight:
                fin_status = "INVALID_WEIGHTAGE"

            budget_util = (project_ev / project_budget * 100.0) if project_budget > 0 else 0.0
            cost_util = (project_ac / project_budget * 100.0) if project_budget > 0 else 0.0

            resp = ProjectResponse.model_validate(p)
            resp.milestones = m_responses
            resp.completion_percentage = sum([m.weight_percentage for m in p.milestones if m.status == "achieved"])
            resp.logged_hours = fin_data["logged_hours"]
            resp.cost = project_ac
            resp.actual_cost = project_ac
            resp.earned_value = project_ev
            resp.budget_utilization_percentage = round(budget_util, 2)
            resp.cost_utilization_percentage = round(cost_util, 2)
            resp.cost_variance = fin_data["cv"]
            resp.cpi = project_cpi
            resp.forecast_cost = project_eac
            resp.financial_status = fin_status
            resp.health = health
            
            resp.revenue = project_ev
            resp.profit = fin_data["cv"]

            if not can_view_budget:
                resp.budget = None
                resp.cost = 0.0
                resp.actual_cost = 0.0
                resp.earned_value = 0.0
                resp.revenue = 0.0
                resp.profit = 0.0
                resp.cost_variance = 0.0
                resp.forecast_cost = 0.0

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

    async def upload_document(self, project_id: int, file: UploadFile) -> ProjectDocumentResponse:
        project = await self.repository.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        dest_dir = Path("uploads") / "projects" / str(project_id)
        saved_path = await save_upload_file(
            file,
            dest_dir,
            allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
            max_size_mb=10.0,
        )

        file_size = saved_path.stat().st_size if saved_path.exists() else None
        # Format web accessible path
        web_path = f"/uploads/projects/{project_id}/{saved_path.name}"

        doc = ProjectDocument(
            project_id=project_id,
            file_name=file.filename,
            file_path=web_path,
            file_size=file_size,
            file_type=file.content_type,
        )
        saved_doc = await self.repository.add_document(doc)
        return ProjectDocumentResponse.model_validate(saved_doc)

    async def delete_document(self, project_id: int, document_id: int) -> None:
        doc = await self.repository.get_document_by_id(document_id)
        if not doc or doc.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        # Delete local file if exists
        rel_path = doc.file_path.lstrip("/")
        delete_file(rel_path)

        await self.repository.delete_document(doc)
