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

    async def calculate_tool_cost_for_period(
        self,
        project_id: int,
        start_date: date,
        end_date: date,
    ) -> float:
        """
        Calculates tool allocation cost overlapping with a given period.
        """
        query = (
            select(ToolAllocation)
            .options(selectinload(ToolAllocation.tool))
            .where(
                ToolAllocation.project_id == project_id,
                ToolAllocation.status == "Active",
                ToolAllocation.allocation_date <= end_date,
            )
        )
        result = await self.db.execute(query)
        allocations = result.scalars().all()

        today = date.today()
        total_tool_cost = 0.0

        for ta in allocations:
            if not ta.tool or ta.tool.cost_per_month <= 0:
                continue

            tool_start = max(ta.allocation_date, start_date)
            tool_end_raw = ta.deallocation_date if ta.deallocation_date else today
            tool_end = min(tool_end_raw, end_date)

            if tool_end < tool_start:
                continue

            monthly_cost = ta.tool.cost_per_month
            basis = getattr(ta, "allocation_basis", "working_day") or "working_day"

            if basis == "calendar_day":
                calendar_days = (tool_end - tool_start).days + 1
                daily_rate = monthly_cost / 30.44
                total_tool_cost += daily_rate * calendar_days

            elif basis == "working_day":
                working_days = await get_working_days(tool_start, tool_end, self.db)
                cal = await _get_working_calendar(self.db)
                wd_config = cal.working_days or {}
                wd_per_week = sum(1 for d in _WEEKDAY_KEYS if wd_config.get(d, False))
                wd_per_month = (wd_per_week * 52) / 12 if wd_per_week > 0 else 22
                daily_rate = monthly_cost / wd_per_month
                total_tool_cost += daily_rate * working_days

            elif basis == "week":
                calendar_days = (tool_end - tool_start).days + 1
                weeks = max(1, calendar_days / 7)
                weekly_rate = monthly_cost / 4.0
                total_tool_cost += weekly_rate * weeks

            elif basis == "month":
                calendar_days = (tool_end - tool_start).days + 1
                months = max(0.0, calendar_days / 30.44)
                total_tool_cost += monthly_cost * months

        return round(total_tool_cost, 2)

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
            cost_end_date = milestone.actual_achievement_date.date() if milestone.actual_achievement_date else today
            if m_start <= cost_end_date:
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
                        billable_hours += float(row.billable)
                        non_billable_hours += float(row.non_billable)
                        user = users.get(row.user_id)
                        if user and user.ctc:
                            hourly_rate = await get_hourly_cost(user.ctc, self.db)
                            m_actual_cost += float(row.billable) * hourly_rate

                # 2. Tool Cost
                tool_cost = await self.calculate_tool_cost_for_period(
                    milestone.project_id, m_start, cost_end_date
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
            tool_cost = await self.calculate_tool_cost_for_period(project.id, start_date, today)
            
            # Labor Cost
            query = (
                select(
                    Timesheet.user_id,
                    func.coalesce(func.sum(Timesheet.billable_hours), 0.0).label("billable"),
                    func.coalesce(func.sum(Timesheet.non_billable_hours), 0.0).label("non_billable"),
                )
                .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
                .where(ProjectAssignment.project_id == project.id)
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
