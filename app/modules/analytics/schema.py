from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class TeamUtilizationUserMetric(BaseModel):
    user_id: int
    user_name: str
    user_avatar: Optional[str] = None
    user_title: Optional[str] = None
    user_department: Optional[str] = None
    total_logged: float
    billable_hours: float
    non_billable_hours: float
    utilization_pct: int
    assigned_pm_projects: List[dict]  # [{"id": 1, "code": "PRJ-1"}]
    status_category: str  # "high", "optimal", "low"

    model_config = ConfigDict(from_attributes=True)


class TeamUtilizationSummary(BaseModel):
    total_billable: float
    total_logged_all: float
    avg_utilization: int
    high_count: int
    optimal_count: int
    low_count: int
    metrics: List[TeamUtilizationUserMetric]

    model_config = ConfigDict(from_attributes=True)


class ProjectFinancialsMetric(BaseModel):
    project_id: int
    project_name: str
    client_name: str
    budget: float
    spent: float
    remaining: float
    burn_rate_pct: int
    status: str
    pm_name: str

    model_config = ConfigDict(from_attributes=True)


class ProjectFinancialsSummary(BaseModel):
    total_budget: float
    total_spent: float
    total_remaining: float
    avg_burn_rate_pct: int
    projects: List[ProjectFinancialsMetric]

    model_config = ConfigDict(from_attributes=True)
