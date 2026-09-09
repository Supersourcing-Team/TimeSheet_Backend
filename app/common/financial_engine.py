import logging
from datetime import date
from typing import List, Dict, Optional, Tuple, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.working_days_calculator import (
    get_working_days,
    get_available_hours,
    get_hourly_cost,
    get_tool_hourly_rate,
    _get_working_calendar,
    _WEEKDAY_KEYS
)
from app.modules.milestones.model import Milestone
from app.modules.projects.model import Project
from app.modules.tool_allocations.model import ToolAllocation
from app.modules.timesheets.model import Timesheet
from app.modules.project_assignments.model import ProjectAssignment
from app.modules.users.model import User


class FinancialEngine:
    def __init__(self, db: AsyncSession):
        self.db = db



    async def calculate_tool_cost_for_milestone(
        self,
        milestone_id: int,
        milestone_hours_logged: float,
    ) -> float:
        """
        Calculates milestone tool cost using the standardized engineering economics hourly rate formula:
        1. Hourly Tool Rate = [MONTHLY_TOOL_COST] / 22 working days / 8 hours
                            = [MONTHLY_TOOL_COST] / 176 hours
        2. Total Milestone Tool Cost = Hourly Tool Rate * [MILESTONE_HOURS_LOGGED]
        """
        if milestone_hours_logged <= 0:
            return 0.0

        query = (
            select(ToolAllocation)
            .options(selectinload(ToolAllocation.tool))
            .where(
                ToolAllocation.milestone_id == milestone_id,
                ToolAllocation.status == "Active",
            )
        )
        result = await self.db.execute(query)
        allocations = result.scalars().all()

        total_hourly_tool_rate = 0.0

        for ta in allocations:
            monthly_cost = getattr(ta, "monthly_cost", None)
            if monthly_cost is None or monthly_cost <= 0:
                monthly_cost = ta.tool.cost_per_month if ta.tool else 0.0

            if monthly_cost <= 0:
                continue

            hourly_rate = await get_tool_hourly_rate(monthly_cost, self.db)
            total_hourly_tool_rate += hourly_rate

        return round(total_hourly_tool_rate * milestone_hours_logged, 2)

    async def calculate_milestone_financials(
        self,
        milestone: Milestone,
        project_budget: float,
    ) -> Dict[str, Any]:
        """
        Calculates AC, EV, PV, CV, CPI, EAC, and ETC for a milestone using Timesheet data.
        """
        today = date.today()
        m_start = milestone.start_date
        m_end_expected = milestone.expected_completion_date

        # Planned Value (PV)
        m_pv = project_budget * ((milestone.weight_percentage or 0.0) / 100.0)

        # Earned Value (EV)
        comp_pct = milestone.completion_percentage or 0.0
        if milestone.status == "achieved":
            comp_pct = 100.0
        m_ev = m_pv * (comp_pct / 100.0)

        m_actual_cost = 0.0
        billable_hours = 0.0
        non_billable_hours = 0.0
        tool_cost = 0.0

        if m_start and m_end_expected:
            if milestone.actual_achievement_date:
                cost_end_date = milestone.actual_achievement_date.date()
            else:
                cost_end_date = m_end_expected
                
            # 1. Timesheet Labor Cost
            query = (
                select(
                    Timesheet.user_id,
                    func.coalesce(func.sum(Timesheet.billable_hours), 0.0).label("billable"),
                    func.coalesce(func.sum(Timesheet.non_billable_hours), 0.0).label("non_billable"),
                )
                .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
                .where(
                    ProjectAssignment.project_id == milestone.project_id,
                    Timesheet.timesheet_date >= m_start,
                    Timesheet.timesheet_date <= cost_end_date,
                    Timesheet.status == "submitted",
                )
                .group_by(Timesheet.user_id)
            )
            result = await self.db.execute(query)
            user_hours = result.all()

            if user_hours:
                user_ids = [row.user_id for row in user_hours]
                u_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
                users = {u.id: u for u in u_result.scalars().all()}

            if user_hours:
                for row in user_hours:
                    billable_hours += float(row.billable)
                    non_billable_hours += float(row.non_billable)
                    user = users.get(row.user_id)
                    if user and user.ctc:
                        hourly_rate = await get_hourly_cost(user.ctc, self.db)
                        m_actual_cost += float(row.billable) * hourly_rate

            logged_hours = billable_hours + non_billable_hours
            tool_cost = await self.calculate_tool_cost_for_milestone(
                milestone.id, logged_hours
            )
            m_actual_cost += tool_cost

        # Cost Variance & CPI
        m_cv = m_ev - m_actual_cost
        m_cpi = m_ev / m_actual_cost if m_actual_cost > 0 else (1.0 if m_ev >= 0 else 0.0)

        # Forecast (EAC - Estimate at Completion)
        if str(milestone.status).lower() in ["achieved", "completed", "cancelled"] or comp_pct >= 100:
            m_eac = m_actual_cost
        else:
            if comp_pct < 10:
                m_eac = m_pv
            else:
                m_eac = m_actual_cost + ((m_pv - m_ev) / max(m_cpi, 0.5))

        return {
            "pv": round(m_pv, 2),
            "ev": round(m_ev, 2),
            "ac": round(m_actual_cost, 2),
            "cv": round(m_cv, 2),
            "cpi": round(m_cpi, 2),
            "eac": round(m_eac, 2),
            "billable_hours": round(billable_hours, 2),
            "non_billable_hours": round(non_billable_hours, 2),
            "tool_cost": round(tool_cost, 2),
            "budget": round(m_pv, 2),
        }

    async def compute_project_financials(self, project: Project) -> Dict[str, Any]:
        """
        Computes aggregate project financials based on milestone financials.
        """
        project_budget = float(project.budget or 0.0)
        
        milestones = project.milestones if hasattr(project, 'milestones') else []
        
        total_pv = 0.0
        total_ev = 0.0
        total_ac = 0.0
        total_eac = 0.0
        total_billable_hours = 0.0
        
        milestone_data = []

        for m in milestones:
            m_fin = await self.calculate_milestone_financials(m, project_budget)
            m_fin["milestone_id"] = m.id
            milestone_data.append(m_fin)

            total_pv += m_fin["pv"]
            total_ev += m_fin["ev"]
            total_ac += m_fin["ac"]
            total_eac += m_fin["eac"]
            total_billable_hours += m_fin["billable_hours"]

        # Aggregate Project Level CV and CPI
        project_cv = total_ev - total_ac
        project_cpi = total_ev / total_ac if total_ac > 0 else (1.0 if total_ev >= 0 else 0.0)

        # Fallback if no milestones but project has timesheets/tools
        if not milestones:
            today = date.today()
            start_date = project.start_date or today
            # tool_cost will be calculated after total_billable_hours is aggregated below
            
            # Labor Cost
            query = (
                select(
                    Timesheet.user_id,
                    func.coalesce(func.sum(Timesheet.billable_hours), 0.0).label("billable"),
                    func.coalesce(func.sum(Timesheet.non_billable_hours), 0.0).label("non_billable"),
                )
                .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
                .where(
                    ProjectAssignment.project_id == project.id,
                    Timesheet.status == "submitted"
                )
                .group_by(Timesheet.user_id)
            )
            result = await self.db.execute(query)
            user_hours = result.all()
            
            if user_hours:
                user_ids = [row.user_id for row in user_hours]
                u_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
                users = {u.id: u for u in u_result.scalars().all()}

                for row in user_hours:
                    total_billable_hours += float(row.billable)
                    user = users.get(row.user_id)
                    if user and user.ctc:
                        hourly_rate = await get_hourly_cost(user.ctc, self.db)
                        total_ac += float(row.billable) * hourly_rate
            
            tool_cost = 0.0
            total_ac += tool_cost
            project_cv = -total_ac
            project_cpi = 0.0
            total_eac = total_ac + project_budget
            total_pv = project_budget

        remaining_budget = project_budget - total_ac
        
        return {
            "budget": round(project_budget, 2),
            "pv": round(total_pv, 2),
            "ev": round(total_ev, 2),
            "ac": round(total_ac, 2),
            "cv": round(project_cv, 2),
            "cpi": round(project_cpi, 2),
            "eac": round(total_eac, 2),
            "remaining_budget": round(remaining_budget, 2),
            "logged_hours": round(total_billable_hours, 2),
            "milestone_financials": { m["milestone_id"]: m for m in milestone_data }
        }
