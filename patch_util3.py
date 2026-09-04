import re

with open('app/modules/utilization/service.py', 'r') as f:
    content = f.read()

pattern_dashboard = re.compile(r'    async def get_dashboard\(.*?(?=    async def get_employee_utilization)', re.DOTALL)
new_dashboard = """    async def get_dashboard(
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

"""
content = pattern_dashboard.sub(new_dashboard, content)


pattern_milestone = re.compile(r'    async def get_milestone_utilization\(.*?(?=\Z)', re.DOTALL)
new_milestone = """    async def get_milestone_utilization(
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
"""
content = pattern_milestone.sub(new_milestone, content)

with open('app/modules/utilization/service.py', 'w') as f:
    f.write(content)
print('Replaced')
