from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schema import (
    TeamUtilizationSummary,
    TeamUtilizationUserMetric,
    ProjectFinancialsSummary,
    ProjectFinancialsMetric,
)

class AnalyticsService:
    @staticmethod
    async def get_team_utilization(db: AsyncSession, current_user: User) -> TeamUtilizationSummary:
        is_admin = getattr(current_user.role, "name", None) == "Admin"
        
        # 1. Fetch utilization stats
        rows = await AnalyticsRepository.get_team_utilization(db, current_user.id, is_admin)
        
        BASELINE_EXPECTED_HOURS = 160.0
        
        metrics = []
        total_billable_all = 0.0
        total_logged_all = 0.0
        high_count = 0
        optimal_count = 0
        low_count = 0
        
        for user, total_logged, billable_hours, non_billable_hours in rows:
            utilization_pct = min(100, int((billable_hours / BASELINE_EXPECTED_HOURS) * 100))
            
            if utilization_pct > 85:
                status_category = "high"
                high_count += 1
            elif utilization_pct < 65:
                status_category = "low"
                low_count += 1
            else:
                status_category = "optimal"
                optimal_count += 1
                
            total_billable_all += billable_hours
            total_logged_all += total_logged
            
            # Get assigned projects for this user managed by the current PM
            assigned_projects = await AnalyticsRepository.get_pm_projects(db, user.id, current_user.id, is_admin)
            
            metrics.append(TeamUtilizationUserMetric(
                user_id=user.id,
                user_name=f"{user.first_name} {user.last_name}",
                user_title=getattr(user.role, "name", "Employee"),
                user_department="Engineering", # Defaulting as there's no department column
                total_logged=total_logged,
                billable_hours=billable_hours,
                non_billable_hours=non_billable_hours,
                utilization_pct=utilization_pct,
                assigned_pm_projects=[{"id": p.id, "code": getattr(p, "project_name", f"PRJ-{p.id}")} for p in assigned_projects],
                status_category=status_category
            ))
            
        avg_utilization = int((total_billable_all / (len(rows) * BASELINE_EXPECTED_HOURS)) * 100) if rows else 0
        
        return TeamUtilizationSummary(
            total_billable=total_billable_all,
            total_logged_all=total_logged_all,
            avg_utilization=avg_utilization,
            high_count=high_count,
            optimal_count=optimal_count,
            low_count=low_count,
            metrics=metrics
        )

    @staticmethod
    async def get_project_financials(db: AsyncSession, current_user: User) -> ProjectFinancialsSummary:
        is_admin = getattr(current_user.role, "name", None) == "Admin"
        
        # 1. Fetch project financials
        rows = await AnalyticsRepository.get_project_financials(db, current_user.id, is_admin)
        
        BILLING_RATE = 150.0  # Assumed billing rate per hour
        
        projects = []
        total_budget_all = 0.0
        total_spent_all = 0.0
        
        for project, total_billable_hours in rows:
            budget = float(project.budget) if project.budget else 0.0
            spent = total_billable_hours * BILLING_RATE
            remaining = max(0.0, budget - spent)
            
            burn_rate_pct = min(100, int((spent / budget) * 100)) if budget > 0 else 0
            
            status = "on_track"
            if burn_rate_pct > 90:
                status = "at_risk"
            elif burn_rate_pct > 75:
                status = "warning"
                
            total_budget_all += budget
            total_spent_all += spent
            
            client_name = project.client.client_name if getattr(project, "client", None) else "Internal"
            pm_name = f"{project.manager.first_name} {project.manager.last_name}" if getattr(project, "manager", None) else "Unassigned"
            
            projects.append(ProjectFinancialsMetric(
                project_id=project.id,
                project_name=project.project_name,
                client_name=client_name,
                budget=budget,
                spent=spent,
                remaining=remaining,
                burn_rate_pct=burn_rate_pct,
                status=status,
                pm_name=pm_name
            ))
            
        total_remaining_all = max(0.0, total_budget_all - total_spent_all)
        avg_burn_rate_pct = int((total_spent_all / total_budget_all) * 100) if total_budget_all > 0 else 0
        
        return ProjectFinancialsSummary(
            total_budget=total_budget_all,
            total_spent=total_spent_all,
            total_remaining=total_remaining_all,
            avg_burn_rate_pct=avg_burn_rate_pct,
            projects=projects
        )
