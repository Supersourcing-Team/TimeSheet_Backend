"""
Utilization API — Response schemas for Employee Utilization & Project Cost Control.
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel


# ── KPI Dashboard ────────────────────────────────────────────────────

class CapacityKPI(BaseModel):
    total_employees: int = 0
    available_hours: float = 0.0
    billable_hours: float = 0.0
    non_billable_hours: float = 0.0
    employee_utilization_pct: float = 0.0


class CostKPI(BaseModel):
    employee_cost: float = 0.0
    tool_cost: float = 0.0
    total_actual_cost: float = 0.0


class BudgetKPI(BaseModel):
    total_budget: float = 0.0
    budget_utilization_pct: float = 0.0
    remaining_budget: float = 0.0
    cost_variance: float = 0.0
    cost_variance_pct: float = 0.0


class ForecastKPI(BaseModel):
    forecasted_final_cost: float = 0.0
    projected_overrun: float = 0.0


class UtilizationDashboardResponse(BaseModel):
    capacity: CapacityKPI = CapacityKPI()
    cost: CostKPI = CostKPI()
    budget: BudgetKPI = BudgetKPI()
    forecast: ForecastKPI = ForecastKPI()


# ── Employee-Level Table ─────────────────────────────────────────────

class EmployeeUtilizationRow(BaseModel):
    employee_id: int
    employee_name: str
    available_hours: float = 0.0
    billable_hours: float = 0.0
    non_billable_hours: float = 0.0
    utilization_pct: float = 0.0
    hourly_cost: float = 0.0
    employee_cost: float = 0.0


class EmployeeUtilizationResponse(BaseModel):
    employees: List[EmployeeUtilizationRow] = []
    total_count: int = 0


# ── Milestone-Level Table ────────────────────────────────────────────

class MilestoneUtilizationRow(BaseModel):
    milestone_id: int
    milestone_name: str
    project_id: int
    project_name: str
    status: str = "planned"
    completion_percentage: float = 0.0
    budget: float = 0.0
    planned_hours: float = 0.0
    billable_hours: float = 0.0
    employee_cost: float = 0.0
    tool_cost: float = 0.0
    total_actual_cost: float = 0.0
    budget_utilization_pct: float = 0.0
    remaining_budget: float = 0.0
    cost_variance: float = 0.0
    forecasted_final_cost: float = 0.0
    projected_overrun: float = 0.0
    planned_duration_days: int = 0
    actual_duration_days: int = 0
    schedule_variance_days: int = 0
    schedule_status: str = "pending"  # early | on_time | late | pending
    cpi: float = 0.0                  # Cost Performance Index (EV / AC); surfaced from FinancialEngine


class MilestoneUtilizationResponse(BaseModel):
    milestones: List[MilestoneUtilizationRow] = []
    total_count: int = 0
