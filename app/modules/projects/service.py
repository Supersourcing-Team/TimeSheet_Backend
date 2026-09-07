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

        from sqlalchemy import select, func
        from app.modules.project_assignments.model import ProjectAssignment
        from app.modules.timesheets.model import Timesheet
        from app.modules.milestones.model import Milestone
        from app.modules.milestones.assignment_model import MilestoneAssignment
        from app.modules.milestones.schema import MilestoneResponse
        from datetime import date, datetime

        project_ids = [p.id for p in projects]

        # Get timesheet logged hours and cost
        try:
            stmt = (
                select(
                    ProjectAssignment.project_id,
                    ProjectAssignment.user_id,
                    func.coalesce(func.sum(Timesheet.billable_hours + Timesheet.non_billable_hours), 0.0).label("logged_hours")
                )
                .join(Timesheet, Timesheet.project_assignment_id == ProjectAssignment.id)
                .where(ProjectAssignment.project_id.in_(project_ids))
                .group_by(ProjectAssignment.project_id, ProjectAssignment.user_id)
            )
            res = await db.execute(stmt)
            # project_id -> user_id -> logged_hours
            user_hours_map = {}
            for row in res.all():
                user_hours_map.setdefault(row.project_id, {})[row.user_id] = float(row.logged_hours)
        except Exception:
            user_hours_map = {}
            
        # We need to get users for those project assignments to calculate cost
        # Actually, let's just query users directly for all project assignments
        from app.modules.users.model import User
        try:
            u_stmt = select(ProjectAssignment.project_id, User).join(User, User.id == ProjectAssignment.user_id).where(ProjectAssignment.project_id.in_(project_ids))
            u_res = await db.execute(u_stmt)
            project_users_map = {}
            for pid, u in u_res.all():
                project_users_map.setdefault(pid, {})[u.id] = u
        except Exception:
            project_users_map = {}

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
        is_admin = current_user and current_user.role and current_user.role.name.lower() == "admin"
        can_view_budget = is_ac_manager or is_admin
        
        today = date.today()

        results = []
        for p in projects:
            project_milestones = milestone_map.get(p.id, [])
            
            # Validation: Weightages must sum to 100
            total_weight = sum([float(m.weight_percentage) for m in project_milestones])
            valid_weight = abs(total_weight - 100.0) < 0.001
            
            # 1. Total Project Budget
            project_budget = float(p.budget or 0.0)
            
            # Calculate actual cost for project
            project_actual_cost = 0.0
            project_logged_hours = 0.0
            p_users = project_users_map.get(p.id, {})
            p_hours = user_hours_map.get(p.id, {})
            
            for uid, hours in p_hours.items():
                project_logged_hours += hours
            
            # Calculate actual cost for tools
            project_tool_cost = 0.0
            if hasattr(p, 'tool_allocations') and p.tool_allocations:
                for ta in p.tool_allocations:
                    if ta.tool and ta.tool.cost_per_month > 0:
                        start_date = ta.allocation_date
                        end_date = ta.deallocation_date if ta.deallocation_date else today
                        duration = max(0, (end_date - start_date).days)
                        # Avoid 0 duration if allocated today
                        if duration == 0 and start_date == today:
                            duration = 1
                        daily_tool_cost = ta.tool.cost_per_month / 30.44
                        project_tool_cost += (daily_tool_cost * duration)
                        
            project_actual_cost += project_tool_cost
            
            # Milestone calculations
            m_responses = []
            project_ev = 0.0
            project_forecast_cost = project_tool_cost
            
            for m in project_milestones:
                # Milestone Planned Value
                m_pv = project_budget * (m.weight_percentage / 100.0)
                
                # Override completion if achieved
                comp_pct = m.completion_percentage or 0.0
                if str(m.status).lower() == "achieved":
                    comp_pct = 100.0
                    
                # Earned Value
                m_ev = m_pv * (comp_pct / 100.0)
                project_ev += m_ev
                
                # Delay Days
                delay_days = 0
                if m.actual_start_date and m.expected_completion_date: # Using expected_completion_date as planned_end_date for now
                    end_date_to_use = m.actual_achievement_date.date() if m.actual_achievement_date else today
                    delay_days = max(0, (end_date_to_use - m.expected_completion_date).days)
                
                # Duration Days
                planned_duration = 0
                if m.start_date and m.expected_completion_date:
                    planned_duration = max(0, (m.expected_completion_date - m.start_date).days)
                
                actual_duration = 0
                start_date_to_use = m.actual_start_date or m.start_date or p.start_date
                if start_date_to_use:
                    end_date_to_use = m.actual_achievement_date.date() if m.actual_achievement_date else today
                    actual_duration = max(1, (end_date_to_use - start_date_to_use).days) # min 1 day if started
                
                # We need a rough estimate of Actual Cost per milestone for the response. 
                # If we don't have exact timesheet entries per milestone, we can estimate by duration or weightage.
                # PRD says: "AC = SUM(employeeDailyCost x actualAllocatedDays x allocationPercentage)"
                m_actual_cost = 0.0
                if actual_duration > 0:
                    if m.assignments and len(m.assignments) > 0:
                        for assignment in m.assignments:
                            if assignment.is_active and assignment.user and assignment.user.ctc:
                                daily_cost = (assignment.user.ctc / 12.0) / 22.0
                                m_actual_cost += (daily_cost * actual_duration) # Assume 100% allocation
                    else:
                        # Fallback: Use all users assigned to the project team
                        if hasattr(p, 'assignments') and p.assignments:
                            for assignment in p.assignments:
                                if assignment.is_active and assignment.user and assignment.user.ctc:
                                    daily_cost = (assignment.user.ctc / 12.0) / 22.0
                                    m_actual_cost += (daily_cost * actual_duration) # Assume 100% allocation
                
                # Accumulate Milestone AC into Project AC
                project_actual_cost += m_actual_cost

                # CPI and CV
                m_cv = m_ev - m_actual_cost
                m_cpi = m_ev / m_actual_cost if m_actual_cost > 0 else (1.0 if m_ev >= 0 else 0.0)
                
                # Forecast
                m_forecast_cost = m_actual_cost
                if str(m.status).lower() not in ["achieved", "completed", "cancelled"] and comp_pct < 100:
                    if actual_duration > 0 and m_actual_cost > 0:
                        run_rate = m_actual_cost / actual_duration
                        remaining_days = max(0, planned_duration - actual_duration) if delay_days == 0 else 0
                        # Very simple remaining cost
                        estimated_remaining_cost = run_rate * remaining_days
                        m_forecast_cost = m_actual_cost + estimated_remaining_cost
                    else:
                        m_forecast_cost = m_pv # fallback
                
                project_forecast_cost += m_forecast_cost
                
                m_resp = MilestoneResponse.model_validate(m)
                m_resp.completion_percentage = comp_pct
                m_resp.planned_value = round(m_pv, 2)
                m_resp.earned_value = round(m_ev, 2)
                m_resp.actual_cost = round(m_actual_cost, 2)
                m_resp.forecast_cost = round(m_forecast_cost, 2)
                m_resp.cost_variance = round(m_cv, 2)
                m_resp.cpi = round(m_cpi, 2)
                m_resp.delay_days = delay_days
                m_resp.planned_duration_days = planned_duration
                m_resp.actual_duration_days = actual_duration
                m_responses.append(m_resp)
            
            # Project level metrics
            project_cv = project_ev - project_actual_cost
            project_cpi = project_ev / project_actual_cost if project_actual_cost > 0 else (1.0 if project_ev >= 0 else 0.0)
            
            budget_util = (project_ev / project_budget * 100.0) if project_budget > 0 else 0.0
            cost_util = (project_actual_cost / project_budget * 100.0) if project_budget > 0 else 0.0
            
            # Health
            health = "GREEN"
            fin_status = "FORECAST_WITHIN_BUDGET"
            
            total_delay = sum([m.delay_days or 0 for m in m_responses])
            if project_forecast_cost > project_budget:
                fin_status = "FORECAST_OVER_BUDGET"
            
            if total_delay > 10 or project_cpi < 0.85 or project_forecast_cost > project_budget:
                health = "RED"
            elif total_delay > 5 or project_cpi < 1.0 or (project_forecast_cost / project_budget) > 0.9 if project_budget > 0 else False:
                health = "AMBER"

            if not valid_weight:
                fin_status = "INVALID_WEIGHTAGE"

            resp = ProjectResponse.model_validate(p)
            resp.milestones = m_responses
            resp.completion_percentage = sum([m.weight_percentage for m in project_milestones if m.status == "achieved"])
            resp.logged_hours = round(project_logged_hours, 2)
            resp.cost = round(project_actual_cost, 2)
            resp.actual_cost = round(project_actual_cost, 2)
            resp.earned_value = round(project_ev, 2)
            resp.budget_utilization_percentage = round(budget_util, 2)
            resp.cost_utilization_percentage = round(cost_util, 2)
            resp.cost_variance = round(project_cv, 2)
            resp.cpi = round(project_cpi, 2)
            resp.forecast_cost = round(project_forecast_cost, 2)
            resp.financial_status = fin_status
            resp.health = health
            
            # Deprecated fields
            resp.revenue = round(project_ev, 2)
            resp.profit = round(project_cv, 2)

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
