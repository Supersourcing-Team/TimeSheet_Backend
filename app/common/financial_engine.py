from datetime import date
from typing import Dict, Any, List, Set, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.working_days_calculator import (
    DEFAULT_HOURLY_RATE,
    get_hourly_cost,
    get_tool_hourly_rate,
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
        cost_end_date: Optional[date] = None,
    ) -> float:
        """
        Calculates milestone tool cost supporting all 4 allocation bases (Bug #51):
        1. 'working_day' and 'week': Duration/hourly rate based on logged timesheet hours.
        2. 'month' and 'calendar_day': Fixed subscription cost pro-rated by allocation-to-deallocation date range.
        """
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

        total_tool_cost = 0.0

        for ta in allocations:
            monthly_cost = getattr(ta, "monthly_cost", None)
            if monthly_cost is None or monthly_cost <= 0:
                monthly_cost = ta.tool.cost_per_month if ta.tool else 0.0

            if monthly_cost <= 0:
                continue

            seats = getattr(ta, "seats", 1) or 1
            if seats <= 0:
                seats = 1
            allocation_total_monthly_cost = monthly_cost * seats
            basis = getattr(ta, "allocation_basis", "working_day") or "working_day"

            if basis in ["working_day", "week"]:
                if milestone_hours_logged > 0:
                    hourly_rate = await get_tool_hourly_rate(
                        allocation_total_monthly_cost, self.db, allocation_basis=basis
                    )
                    total_tool_cost += hourly_rate * milestone_hours_logged
            elif basis in ["calendar_day", "month"]:
                # Fixed subscription cost pro-rated by allocation date range
                alloc_start = getattr(ta, "allocation_date", None) or date.today()
                alloc_end = getattr(ta, "deallocation_date", None)
                if alloc_end is None:
                    alloc_end = cost_end_date or date.today()
                elif cost_end_date and alloc_end > cost_end_date:
                    alloc_end = cost_end_date
                if alloc_end < alloc_start:
                    alloc_end = alloc_start
                duration_days = (alloc_end - alloc_start).days + 1

                if basis == "calendar_day":
                    daily_rate = allocation_total_monthly_cost / 30.4167
                    total_tool_cost += daily_rate * duration_days
                else:  # "month" (Monthly flat pro-rated)
                    months_fraction = duration_days / 30.4167
                    total_tool_cost += allocation_total_monthly_cost * months_fraction

        return round(total_tool_cost, 2)

    async def calculate_milestone_financials(
        self,
        milestone: Milestone,
        project_budget: float,
    ) -> Dict[str, Any]:
        """
        Calculates AC, EV, PV, CV, CPI, EAC, and ETC for a milestone using Timesheet data.
        """
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
        missing_ctc_users: Set[int] = set()

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
                    Timesheet.status.in_(["submitted", "approved"]),
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
                    user_ctc = user.ctc if user else None
                    if not user_ctc or user_ctc <= 0:
                        missing_ctc_users.add(row.user_id)
                    hourly_rate = await get_hourly_cost(user_ctc, self.db)
                    m_actual_cost += float(row.billable) * hourly_rate

            logged_hours = billable_hours + non_billable_hours
            tool_cost = await self.calculate_tool_cost_for_milestone(
                milestone.id, logged_hours, cost_end_date=cost_end_date
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
            "has_missing_ctc": len(missing_ctc_users) > 0,
            "missing_ctc_user_ids": sorted(list(missing_ctc_users)),
        }

    async def compute_project_financials(self, project: Project) -> Dict[str, Any]:
        """
        Computes aggregate project financials.
        
        Milestone-level financials (PV, EV, EAC, milestone AC) are calculated per milestone.
        Project-level actual labor cost and hours are calculated directly from all eligible
        project timesheets (submitted or approved) so that timesheets on overlapping milestone
        boundary dates are never double-counted, and timesheets outside milestone date windows
        are never omitted.
        
        Tool costs from all active milestone tool allocations are added to the labor cost.
        """
        project_budget = float(project.budget or 0.0)
        milestones = project.milestones if hasattr(project, "milestones") else []

        total_pv = 0.0
        total_ev = 0.0
        total_eac = 0.0
        milestone_data = []

        total_tool_cost = 0.0

        for m in milestones:
            m_fin = await self.calculate_milestone_financials(m, project_budget)
            m_fin["milestone_id"] = m.id
            milestone_data.append(m_fin)

            total_pv += m_fin["pv"]
            total_ev += m_fin["ev"]
            total_eac += m_fin["eac"]
            total_tool_cost += m_fin.get("tool_cost", 0.0)

        # 1. Project-Level Direct Labor Cost & Hours from all eligible timesheets
        query = (
            select(
                Timesheet.user_id,
                func.coalesce(func.sum(Timesheet.billable_hours), 0.0).label("billable"),
                func.coalesce(func.sum(Timesheet.non_billable_hours), 0.0).label("non_billable"),
            )
            .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
            .where(
                ProjectAssignment.project_id == project.id,
                Timesheet.status.in_(["submitted", "approved"]),
            )
            .group_by(Timesheet.user_id)
        )
        result = await self.db.execute(query)
        user_hours = result.all()

        total_billable_hours = 0.0
        total_non_billable_hours = 0.0
        project_labor_cost = 0.0
        missing_ctc_users: Set[int] = set()

        if user_hours:
            user_ids = [row.user_id for row in user_hours]
            u_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
            users = {u.id: u for u in u_result.scalars().all()}

            for row in user_hours:
                b_hours = float(row.billable)
                nb_hours = float(row.non_billable)
                total_billable_hours += b_hours
                total_non_billable_hours += nb_hours
                user = users.get(row.user_id)
                user_ctc = user.ctc if user else None
                if not user_ctc or user_ctc <= 0:
                    missing_ctc_users.add(row.user_id)
                hourly_rate = await get_hourly_cost(user_ctc, self.db)
                project_labor_cost += b_hours * hourly_rate

        total_logged_hours = total_billable_hours + total_non_billable_hours
        total_ac = project_labor_cost + total_tool_cost

        # Fallback EV, PV, EAC adjustments if project has no milestones
        if not milestones:
            total_pv = project_budget
            project_cv = -total_ac
            project_cpi = 0.0
            total_eac = total_ac + project_budget
        else:
            project_cv = total_ev - total_ac
            project_cpi = total_ev / total_ac if total_ac > 0 else (1.0 if total_ev >= 0 else 0.0)

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
            "logged_hours": round(total_logged_hours, 2),
            "billable_hours": round(total_billable_hours, 2),
            "non_billable_hours": round(total_non_billable_hours, 2),
            "labor_cost": round(project_labor_cost, 2),
            "tool_cost": round(total_tool_cost, 2),
            "has_missing_ctc": len(missing_ctc_users) > 0,
            "missing_ctc_user_ids": sorted(list(missing_ctc_users)),
            "milestone_financials": {m["milestone_id"]: m for m in milestone_data},
        }

