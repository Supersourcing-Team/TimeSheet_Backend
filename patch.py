import re

with open('app/modules/projects/service.py', 'r') as f:
    content = f.read()

pattern = re.compile(r'    @staticmethod\s+async def compute_financials_for_projects\(.*?\n        return results', re.DOTALL)

new_method = """    @staticmethod
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

        return results"""

new_content = pattern.sub(new_method, content)

with open('app/modules/projects/service.py', 'w') as f:
    f.write(new_content)
print('Replaced')
