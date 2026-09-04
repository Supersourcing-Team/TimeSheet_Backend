"""
Utilization Service — Core business logic for Employee Utilization & Project Cost Control.

Implements the full data flow:
  Employee Master (CTC) → Hourly Cost
  Milestone (Start → Expected End) → Available Hours (via Working Days Calculator)
  Timesheets (Billable Hours) → Employee Utilization & Cost
  Tool Allocations → Tool Cost per Milestone
  Budget → Budget Utilization, Cost Variance, Forecast
"""

from datetime import date
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.working_days_calculator import (
    get_working_days,
    get_available_hours,
    get_hourly_cost,
)
from app.modules.milestones.model import Milestone
from app.modules.milestones.assignment_model import MilestoneAssignment
from app.modules.projects.model import Project
from app.modules.project_assignments.model import ProjectAssignment
from app.modules.timesheets.model import Timesheet
from app.modules.tool_allocations.model import ToolAllocation
from app.modules.tools.model import Tool
from app.modules.users.model import User
from app.modules.utilization.schema import (
    CapacityKPI,
    CostKPI,
    BudgetKPI,
    ForecastKPI,
    UtilizationDashboardResponse,
    EmployeeUtilizationRow,
    EmployeeUtilizationResponse,
    MilestoneUtilizationRow,
    MilestoneUtilizationResponse,
)


class UtilizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────────
    # Tool cost calculation (allocation-basis aware)
    # ──────────────────────────────────────────────────────────────

    async def _calculate_tool_cost_for_milestone(
        self,
        project_id: int,
        milestone_start: date,
        milestone_end: date,
    ) -> float:
        """
        Calculate total tool cost allocated to a milestone period.

        Supports allocation bases: working_day, calendar_day, week, month.
        """
        query = (
            select(ToolAllocation)
            .options(selectinload(ToolAllocation.tool))
            .where(
                ToolAllocation.project_id == project_id,
                ToolAllocation.status == "Active",
                ToolAllocation.allocation_date <= milestone_end,
            )
        )
        result = await self.db.execute(query)
        allocations = result.scalars().all()

        today = date.today()
        total_tool_cost = 0.0

        for ta in allocations:
            if not ta.tool or ta.tool.cost_per_month <= 0:
                continue

            # Determine effective overlap period
            tool_start = max(ta.allocation_date, milestone_start)
            tool_end_raw = ta.deallocation_date if ta.deallocation_date else today
            tool_end = min(tool_end_raw, milestone_end)

            if tool_end < tool_start:
                continue  # No overlap

            monthly_cost = ta.tool.cost_per_month
            basis = getattr(ta, "allocation_basis", "working_day") or "working_day"

            if basis == "calendar_day":
                calendar_days = (tool_end - tool_start).days + 1
                # Average calendar days per month ≈ 30.44
                daily_rate = monthly_cost / 30.44
                total_tool_cost += daily_rate * calendar_days

            elif basis == "working_day":
                working_days = await get_working_days(tool_start, tool_end, self.db)
                # Working days per month from calendar config
                from app.common.working_days_calculator import _get_working_calendar, _WEEKDAY_KEYS
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

    # ──────────────────────────────────────────────────────────────
    # Auto-allocate timesheets to milestones by date overlap
    # ──────────────────────────────────────────────────────────────

    async def _get_timesheet_hours_for_milestone(
        self,
        project_id: int,
        milestone_start: Optional[date],
        milestone_end: Optional[date],
    ) -> Dict[int, Tuple[float, float]]:
        """
        Find all timesheets within the milestone date range for this project's employees.

        Returns: {user_id: (billable_hours, non_billable_hours)}

        Only employees who have actually filed timesheets are included.
        """
        if not milestone_start or not milestone_end:
            return {}

        query = (
            select(
                Timesheet.user_id,
                func.coalesce(func.sum(Timesheet.billable_hours), 0.0).label("billable"),
                func.coalesce(func.sum(Timesheet.non_billable_hours), 0.0).label("non_billable"),
            )
            .join(ProjectAssignment, Timesheet.project_assignment_id == ProjectAssignment.id)
            .where(
                ProjectAssignment.project_id == project_id,
                Timesheet.timesheet_date >= milestone_start,
                Timesheet.timesheet_date <= milestone_end,
            )
            .group_by(Timesheet.user_id)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return {row.user_id: (float(row.billable), float(row.non_billable)) for row in rows}

    async def _get_user_map(self, user_ids: List[int]) -> Dict[int, User]:
        """Fetch users by IDs."""
        if not user_ids:
            return {}
        result = await self.db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        return {u.id: u for u in users}

    # ──────────────────────────────────────────────────────────────
    # Load milestones for given filters
    # ──────────────────────────────────────────────────────────────

    async def _load_milestones(
        self,
        project_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        milestone_status: Optional[str] = None,
    ) -> List[Milestone]:
        query = (
            select(Milestone)
            .options(
                selectinload(Milestone.project),
                selectinload(Milestone.assignments).selectinload(MilestoneAssignment.user),
            )
        )
        if project_id:
            query = query.where(Milestone.project_id == project_id)
        if milestone_id:
            query = query.where(Milestone.id == milestone_id)
        if milestone_status:
            query = query.where(Milestone.status == milestone_status)

        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    # ──────────────────────────────────────────────────────────────
    # ENDPOINT 1: Dashboard KPIs
    # ──────────────────────────────────────────────────────────────

    async def get_dashboard(
        self,
        project_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        milestone_status: Optional[str] = None,
    ) -> UtilizationDashboardResponse:
        from app.common.financial_engine import FinancialEngine
        engine = FinancialEngine(self.db)
        milestones = await self._load_milestones(project_id, milestone_id, milestone_status)

        total_available_hours = 0.0
        total_billable_hours = 0.0
        total_non_billable_hours = 0.0
        total_actual_cost = 0.0
        total_tool_cost = 0.0
        total_budget = 0.0
        all_employee_ids = set()
        overall_completion_weighted = 0.0
        overall_weight = 0.0

        for m in milestones:
            m_start = m.start_date
            m_end = m.expected_completion_date
            project_budget = float(m.project.budget or 0.0) if m.project else 0.0
            fin_data = await engine.calculate_milestone_financials(m, project_budget)
            
            if m_start and m_end:
                assigned_members_count = sum(1 for a in m.assignments if a.is_active)
                if assigned_members_count == 0:
                    assigned_members_count = 1

                m_available = await get_available_hours(m_start, m_end, self.db)
                total_available_hours += (m_available * assigned_members_count)

                user_hours = await self._get_timesheet_hours_for_milestone(m.project_id, m_start, m_end)
                all_employee_ids.update(user_hours.keys())
            
            total_billable_hours += fin_data["billable_hours"]
            total_non_billable_hours += fin_data["non_billable_hours"]
            
            total_actual_cost += fin_data["ac"]
            total_tool_cost += fin_data["tool_cost"]
            total_budget += fin_data["budget"]

            comp_pct = m.completion_percentage or 0.0
            if m.status == "achieved":
                comp_pct = 100.0
            overall_completion_weighted += comp_pct * (m.weight_percentage or 0.0)
            overall_weight += (m.weight_percentage or 0.0)

        utilization_pct = (total_billable_hours / total_available_hours * 100.0) if total_available_hours > 0 else 0.0
        budget_util_pct = (total_actual_cost / total_budget * 100.0) if total_budget > 0 else 0.0
        remaining = total_budget - total_actual_cost
        cv = total_budget - total_actual_cost
        cv_pct = (cv / total_budget * 100.0) if total_budget > 0 else 0.0

        avg_completion = (overall_completion_weighted / overall_weight) if overall_weight > 0 else 0.0
        if avg_completion > 0:
            forecast = total_actual_cost / (avg_completion / 100.0)
        else:
            forecast = total_actual_cost
        overrun = max(0.0, forecast - total_budget)

        total_employee_cost = total_actual_cost - total_tool_cost

        return UtilizationDashboardResponse(
            capacity=CapacityKPI(
                total_employees=len(all_employee_ids),
                available_hours=round(total_available_hours, 2),
                billable_hours=round(total_billable_hours, 2),
                non_billable_hours=round(total_non_billable_hours, 2),
                employee_utilization_pct=round(utilization_pct, 2),
            ),
            cost=CostKPI(
                employee_cost=round(total_employee_cost, 2),
                tool_cost=round(total_tool_cost, 2),
                total_actual_cost=round(total_actual_cost, 2),
            ),
            budget=BudgetKPI(
                total_budget=round(total_budget, 2),
                budget_utilization_pct=round(budget_util_pct, 2),
                remaining_budget=round(remaining, 2),
                cost_variance=round(cv, 2),
                cost_variance_pct=round(cv_pct, 2),
            ),
            forecast=ForecastKPI(
                forecasted_final_cost=round(forecast, 2),
                projected_overrun=round(overrun, 2),
            ),
        )

    async def get_employee_utilization(
        self,
        project_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        milestone_status: Optional[str] = None,
    ) -> EmployeeUtilizationResponse:
        milestones = await self._load_milestones(project_id, milestone_id, milestone_status)

        # Aggregate per employee across all matching milestones
        emp_data: Dict[int, dict] = {}  # uid -> {billable, non_billable, available}

        for m in milestones:
            m_start = m.start_date
            m_end = m.expected_completion_date
            if not m_start or not m_end:
                continue

            m_available = await get_available_hours(m_start, m_end, self.db)
            user_hours = await self._get_timesheet_hours_for_milestone(
                m.project_id, m_start, m_end
            )

            for uid, (billable, non_billable) in user_hours.items():
                if uid not in emp_data:
                    emp_data[uid] = {"billable": 0.0, "non_billable": 0.0, "available": 0.0}
                emp_data[uid]["billable"] += billable
                emp_data[uid]["non_billable"] += non_billable
                emp_data[uid]["available"] += m_available

        if not emp_data:
            return EmployeeUtilizationResponse(employees=[], total_count=0)

        user_map = await self._get_user_map(list(emp_data.keys()))

        rows = []
        for uid, data in emp_data.items():
            user = user_map.get(uid)
            if not user:
                continue

            billable = data["billable"]
            non_billable = data["non_billable"]
            available = data["available"]
            util_pct = (billable / available * 100.0) if available > 0 else 0.0
            hourly = await get_hourly_cost(user.ctc or 0.0, self.db)
            emp_cost = billable * hourly

            rows.append(EmployeeUtilizationRow(
                employee_id=uid,
                employee_name=f"{user.first_name} {user.last_name}",
                available_hours=round(available, 2),
                billable_hours=round(billable, 2),
                non_billable_hours=round(non_billable, 2),
                utilization_pct=round(util_pct, 2),
                hourly_cost=hourly,
                employee_cost=round(emp_cost, 2),
            ))

        # Sort by utilization descending
        rows.sort(key=lambda r: r.utilization_pct, reverse=True)

        return EmployeeUtilizationResponse(employees=rows, total_count=len(rows))

    # ──────────────────────────────────────────────────────────────
    # ENDPOINT 3: Milestone-Level Cost Table
    # ──────────────────────────────────────────────────────────────

    async def get_milestone_utilization(
        self,
        project_id: Optional[int] = None,
        milestone_id: Optional[int] = None,
        milestone_status: Optional[str] = None,
    ) -> MilestoneUtilizationResponse:
        from app.common.financial_engine import FinancialEngine
        engine = FinancialEngine(self.db)
        milestones = await self._load_milestones(project_id, milestone_id, milestone_status)
        today = date.today()

        rows = []
        for m in milestones:
            m_start = m.start_date
            m_end = m.expected_completion_date
            project_name = m.project.project_name if m.project else "Unknown"
            project_budget = float(m.project.budget or 0.0) if m.project else 0.0

            fin_data = await engine.calculate_milestone_financials(m, project_budget)
            
            planned_hours = 0.0
            planned_duration = 0
            actual_duration = 0
            
            if m_start and m_end:
                assigned_members_count = sum(1 for a in m.assignments if a.is_active)
                if assigned_members_count == 0:
                    assigned_members_count = 1
                    
                planned_hours = await get_available_hours(m_start, m_end, self.db)
                planned_hours *= assigned_members_count
                planned_duration = await get_working_days(m_start, m_end, self.db)
                
            m_budget = fin_data["budget"]
            total_actual_cost = fin_data["ac"]
            tool_cost = fin_data["tool_cost"]
            total_emp_cost = total_actual_cost - tool_cost
            
            budget_util_pct = (total_actual_cost / m_budget * 100.0) if m_budget > 0 else 0.0
            remaining = m_budget - total_actual_cost
            cv = fin_data["cv"]
            
            comp_pct = m.completion_percentage or 0.0
            if m.status == "achieved":
                comp_pct = 100.0
                
            actual_end = m.actual_achievement_date.date() if m.actual_achievement_date else (today if m.status == "in_progress" else None)
            if actual_end and m_start:
                actual_duration = await get_working_days(m_start, actual_end, self.db)
                
            schedule_variance = actual_duration - planned_duration if actual_duration > 0 and planned_duration > 0 else 0
            
            if m.status == "achieved":
                if m_start and m_end:
                    if schedule_variance < 0:
                        schedule_status = "early"
                    elif schedule_variance == 0:
                        schedule_status = "on_time"
                    else:
                        schedule_status = "late"
                else:
                    schedule_status = "on_time" # if achieved but no dates set
            else:
                schedule_status = "pending"
                
            forecast = fin_data["eac"]
            overrun = max(0.0, forecast - m_budget)
            
            rows.append(MilestoneUtilizationRow(
                milestone_id=m.id,
                milestone_name=m.name,
                project_id=m.project_id,
                project_name=project_name,
                status=m.status,
                completion_percentage=round(comp_pct, 2),
                budget=round(m_budget, 2),
                planned_hours=round(planned_hours, 2),
                billable_hours=round(fin_data["billable_hours"], 2),
                employee_cost=round(total_emp_cost, 2),
                tool_cost=round(tool_cost, 2),
                total_actual_cost=round(total_actual_cost, 2),
                budget_utilization_pct=round(budget_util_pct, 2),
                remaining_budget=round(remaining, 2),
                cost_variance=round(cv, 2),
                forecasted_final_cost=round(forecast, 2),
                projected_overrun=round(overrun, 2),
                planned_duration_days=planned_duration,
                actual_duration_days=actual_duration,
                schedule_variance_days=schedule_variance,
                schedule_status=schedule_status,
                cpi=fin_data["cpi"]
            ))

        return MilestoneUtilizationResponse(milestones=rows, total_count=len(rows))
