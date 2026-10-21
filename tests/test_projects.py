from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.modules.auth.jwt import create_access_token


client = TestClient(app)


class MockRole:
    def __init__(self, id=2, name="Project_Manager"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, role_name="Project_Manager"):
        self.id = id
        self.role = MockRole(name=role_name)


def pm_auth_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


PM_USER = MockUser(id=1, role_name="Project_Manager")


class MockProject:
    def __init__(self, id=1, client_id=1, pm_id=1, name="Project X", budget=1000):
        self.id = id
        self.client_id = client_id
        self.project_manager_id = pm_id
        self.project_name = name
        self.budget = budget
        self.description = "Test project"
        self.start_date = None
        self.end_date = None
        self.status = "Planning"
        self.is_active = True
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def model_dump(self, mode="json"):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "project_manager_id": self.project_manager_id,
            "project_name": self.project_name,
            "budget": self.budget,
            "description": self.description,
            "status": self.status,
            "is_active": self.is_active,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def test_create_project_pm_success():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project X",
        "budget": 1000.50
    }
    created_project = MockProject(budget=1000.50)

    # Need to mock the service layer completely to avoid DB validation calls,
    # OR mock the individual repository calls. Let's mock repository calls.
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.create", return_value=created_project), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=created_project), \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=None)]), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_any_assignment", return_value=True):

        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["project_name"] == "Project X"
        assert json_data["data"]["budget"] is None




def test_create_project_invalid_dates():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project Y",
        "start_date": "2024-12-01",
        "end_date": "2024-11-01"  # End date before start date
    }
    
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        # Should fail Pydantic validation (422)
        assert response.status_code == 422


def test_create_project_invalid_budget():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project Z",
        "budget": -50  # Negative budget
    }
    
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        # Should fail Pydantic validation (422)
        assert response.status_code == 422


AM_USER = MockUser(id=3, role_name="Account_Manager")


def am_auth_headers():
    token = create_access_token(data={"sub": "3", "email": "am@example.com", "role": "Account_Manager", "employee_id": "EMP003"})
    return {"Authorization": f"Bearer {token}"}


def test_am_create_and_view_budget_success():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "AM Project",
        "budget": 500000.0
    }
    created_project = MockProject(id=2, budget=500000.0, name="AM Project")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=AM_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.create", return_value=created_project), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=created_project), \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[created_project]), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_any_assignment", return_value=True):

        response = client.post("/api/v1/projects/", json=payload, headers=am_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["budget"] == 500000.0


# ---------------------------------------------------------------------------
# Bug #5: Project Cost Calculation & Financial Engine Tests
# ---------------------------------------------------------------------------

import pytest
from datetime import date
from unittest.mock import MagicMock
from app.common.financial_engine import FinancialEngine


@pytest.mark.asyncio
async def test_financial_engine_no_double_counting_on_boundary_dates():
    """
    Two milestones sharing a boundary date:
    Timesheet logged on boundary date must contribute to project-level labor cost only ONCE.
    """
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    # Mock Project with 2 contiguous milestones
    m1 = MagicMock()
    m1.id = 1
    m1.project_id = 10
    m1.start_date = date(2026, 8, 1)
    m1.expected_completion_date = date(2026, 8, 15)
    m1.actual_achievement_date = None
    m1.weight_percentage = 50.0
    m1.completion_percentage = 100.0
    m1.status = "achieved"

    m2 = MagicMock()
    m2.id = 2
    m2.project_id = 10
    m2.start_date = date(2026, 8, 15)  # Shared boundary date
    m2.expected_completion_date = date(2026, 8, 31)
    m2.actual_achievement_date = None
    m2.weight_percentage = 50.0
    m2.completion_percentage = 0.0
    m2.status = "in_progress"

    proj = MagicMock()
    proj.id = 10
    proj.budget = 100000.0
    proj.milestones = [m1, m2]

    # Mock milestone financials returning AC for their respective date queries
    # In milestone queries, boundary day was queried by both m1 and m2
    async def mock_milestone_fin(milestone, budget):
        return {
            "pv": 50000.0,
            "ev": 50000.0 if milestone.id == 1 else 0.0,
            "ac": 8000.0,  # 8h * 1000
            "cv": 42000.0,
            "cpi": 1.0,
            "eac": 8000.0,
            "billable_hours": 8.0,
            "non_billable_hours": 0.0,
            "tool_cost": 500.0,
            "budget": 50000.0,
        }

    engine.calculate_milestone_financials = AsyncMock(side_effect=mock_milestone_fin)

    # For project-level direct query: 1 single timesheet record of 8 billable hours on boundary date
    row_mock = MagicMock()
    row_mock.user_id = 1
    row_mock.billable = 8.0
    row_mock.non_billable = 2.0

    user_hours_res = MagicMock()
    user_hours_res.all.return_value = [row_mock]

    user_obj = MagicMock()
    user_obj.id = 1
    user_obj.ctc = 1200000.0  # CTC
    user_res = MagicMock()
    user_res.scalars.return_value.all.return_value = [user_obj]

    mock_db.execute.side_effect = [user_hours_res, user_res]

    with patch("app.common.financial_engine.get_hourly_cost", AsyncMock(return_value=1000.0)):
        fin_data = await engine.compute_project_financials(proj)

    # Labor cost should be 8.0 * 1000 = 8000.0 (NOT 16000.0)
    assert fin_data["labor_cost"] == 8000.0
    # Tool cost from m1 (500) + m2 (500) = 1000.0
    assert fin_data["tool_cost"] == 1000.0
    # Total AC = 8000.0 + 1000.0 = 9000.0
    assert fin_data["ac"] == 9000.0
    # Logged hours = 8.0 billable + 2.0 non_billable = 10.0
    assert fin_data["logged_hours"] == 10.0
    assert fin_data["billable_hours"] == 8.0
    assert fin_data["non_billable_hours"] == 2.0


@pytest.mark.asyncio
async def test_financial_engine_includes_timesheets_outside_milestone_dates():
    """
    Project timesheets logged before milestone start or after milestone completion
    are properly included in project-level actual cost.
    """
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    m1 = MagicMock()
    m1.id = 1
    m1.project_id = 10

    proj = MagicMock()
    proj.id = 10
    proj.budget = 50000.0
    proj.milestones = [m1]

    # Milestone 1 only covered 5 hours
    engine.calculate_milestone_financials = AsyncMock(return_value={
        "pv": 50000.0, "ev": 0.0, "ac": 5000.0, "cv": -5000.0, "cpi": 0.0,
        "eac": 55000.0, "billable_hours": 5.0, "non_billable_hours": 0.0,
        "tool_cost": 0.0, "budget": 50000.0
    })

    # Total project timesheets include 5h inside milestone + 10h outside milestone = 15h total
    row_mock = MagicMock()
    row_mock.user_id = 1
    row_mock.billable = 15.0
    row_mock.non_billable = 3.0

    user_hours_res = MagicMock()
    user_hours_res.all.return_value = [row_mock]

    user_obj = MagicMock()
    user_obj.id = 1
    user_obj.ctc = 1200000.0
    user_res = MagicMock()
    user_res.scalars.return_value.all.return_value = [user_obj]

    mock_db.execute.side_effect = [user_hours_res, user_res]

    with patch("app.common.financial_engine.get_hourly_cost", AsyncMock(return_value=1000.0)):
        fin_data = await engine.compute_project_financials(proj)

    # Project actual cost must reflect all 15 billable hours across the project
    assert fin_data["labor_cost"] == 15000.0
    assert fin_data["ac"] == 15000.0
    assert fin_data["billable_hours"] == 15.0
    assert fin_data["logged_hours"] == 18.0


@pytest.mark.asyncio
async def test_financial_engine_project_without_milestones():
    """Projects without milestones calculate correct actual cost, PV, EV, and EAC."""
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    proj = MagicMock()
    proj.id = 20
    proj.budget = 200000.0
    proj.milestones = []

    row_mock = MagicMock()
    row_mock.user_id = 2
    row_mock.billable = 10.0
    row_mock.non_billable = 0.0

    user_hours_res = MagicMock()
    user_hours_res.all.return_value = [row_mock]

    user_obj = MagicMock()
    user_obj.id = 2
    user_obj.ctc = 600000.0
    user_res = MagicMock()
    user_res.scalars.return_value.all.return_value = [user_obj]

    mock_db.execute.side_effect = [user_hours_res, user_res]

    with patch("app.common.financial_engine.get_hourly_cost", AsyncMock(return_value=500.0)):
        fin_data = await engine.compute_project_financials(proj)

    assert fin_data["labor_cost"] == 5000.0
    assert fin_data["ac"] == 5000.0
    assert fin_data["pv"] == 200000.0
    assert fin_data["remaining_budget"] == 195000.0
    assert fin_data["eac"] == 205000.0


@pytest.mark.asyncio
async def test_financial_engine_missing_or_zero_ctc_handled_safely():
    """Bug #48: Users with None or 0 CTC use safe fallback hourly rate (500.0) and flag missing CTC."""
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    proj = MagicMock()
    proj.id = 30
    proj.budget = 10000.0
    proj.milestones = []

    row_mock = MagicMock()
    row_mock.user_id = 3
    row_mock.billable = 20.0
    row_mock.non_billable = 5.0

    user_hours_res = MagicMock()
    user_hours_res.all.return_value = [row_mock]

    user_obj = MagicMock()
    user_obj.id = 3
    user_obj.ctc = None  # None CTC
    user_res = MagicMock()
    user_res.scalars.return_value.all.return_value = [user_obj]

    mock_db.execute.side_effect = [user_hours_res, user_res]

    fin_data = await engine.compute_project_financials(proj)

    # 20 billable hours * 500.0 fallback hourly rate = 10000.0 labor cost (not 0.0)
    assert fin_data["labor_cost"] == 10000.0
    assert fin_data["ac"] == 10000.0
    assert fin_data["logged_hours"] == 25.0
    assert fin_data["billable_hours"] == 20.0
    assert fin_data["has_missing_ctc"] is True
    assert 3 in fin_data["missing_ctc_user_ids"]


# ---------------------------------------------------------------------------
# Phase 3: Bug #13, Bug #48, Bug #51 Regression Tests
# ---------------------------------------------------------------------------

ADMIN_USER = MockUser(id=99, role_name="Admin")

def admin_auth_headers():
    token = create_access_token(data={"sub": "99"})
    return {"Authorization": f"Bearer {token}"}


def test_create_project_admin_sets_budget_successfully():
    """Bug #13: Admin can enter project budget and it is NOT nullified."""
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Admin Budget Project",
        "budget": 75000.0,
    }
    created_project = MockProject(name="Admin Budget Project", budget=75000.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.create", return_value=created_project), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=created_project), \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=75000.0)]), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_any_assignment", return_value=True):

        response = client.post("/api/v1/projects/", json=payload, headers=admin_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["budget"] == 75000.0


def test_update_project_admin_updates_budget():
    """Bug #13: Admin can modify project budget on update."""
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Updated Budget Project",
        "budget": 90000.0,
    }
    existing_project = MockProject(budget=50000.0)
    updated_project = MockProject(budget=90000.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=existing_project), \
         patch("app.modules.projects.service.ProjectRepository.update", return_value=updated_project), \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=90000.0)]):

        response = client.put("/api/v1/projects/1", json=payload, headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["budget"] == 90000.0


def test_update_project_pm_preserves_existing_budget():
    """Bug #13: When PM updates project, existing budget is preserved rather than wiped to None."""
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "PM Updated Project",
        "budget": 12345.0,  # PM attempts to change budget
    }
    existing_project = MockProject(budget=50000.0)
    # PM cannot change budget, so service must preserve existing_project.budget (50000.0)
    updated_project = MockProject(budget=50000.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=existing_project), \
         patch("app.modules.projects.service.ProjectRepository.update", return_value=updated_project) as mock_update, \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=50000.0)]):

        response = client.put("/api/v1/projects/1", json=payload, headers=pm_auth_headers())
        assert response.status_code == 200
        # Verify repository.update was called with preserved budget (50000.0), NOT None or PM's attempted budget
        call_args = mock_update.call_args[0]
        project_in = call_args[1]
        assert project_in.budget == 50000.0


@pytest.mark.asyncio
async def test_tool_cost_allocation_bases():
    """Bug #51: Test all 4 tool allocation bases (working_day, week, calendar_day, month)."""
    from datetime import date
    from app.modules.tool_allocations.model import ToolAllocation
    from app.common.working_days_calculator import get_tool_hourly_rate

    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    # 1. working_day tool: monthly_cost=1760.0, seats=1 -> 1760 / 176h = 10.0/hr * 20 logged hours = 200.0
    ta_working = MagicMock()
    ta_working.monthly_cost = 1760.0
    ta_working.seats = 1
    ta_working.allocation_basis = "working_day"
    ta_working.status = "Active"

    # 2. week tool: monthly_cost=1733.33, seats=2 -> (1733.33*2) / 173.33h = 20.0/hr * 20 logged hours = 400.0
    ta_week = MagicMock()
    ta_week.monthly_cost = 1733.33
    ta_week.seats = 2
    ta_week.allocation_basis = "week"
    ta_week.status = "Active"

    # 3. calendar_day tool: monthly_cost=304.167, seats=1, 10 days duration -> (304.167/30.4167) * 10 = 100.0
    ta_cal = MagicMock()
    ta_cal.monthly_cost = 304.167
    ta_cal.seats = 1
    ta_cal.allocation_basis = "calendar_day"
    ta_cal.status = "Active"
    ta_cal.allocation_date = date(2026, 9, 1)
    ta_cal.deallocation_date = date(2026, 9, 10)  # 10 days

    # 4. month tool: monthly_cost=500.0, seats=1, 15 days duration -> 500.0 * (15/30.4167) ≈ 246.57
    ta_month = MagicMock()
    ta_month.monthly_cost = 500.0
    ta_month.seats = 1
    ta_month.allocation_basis = "month"
    ta_month.status = "Active"
    ta_month.allocation_date = date(2026, 9, 1)
    ta_month.deallocation_date = date(2026, 9, 15)  # 15 days

    alloc_res = MagicMock()
    alloc_res.scalars.return_value.all.return_value = [ta_working, ta_week, ta_cal, ta_month]
    mock_db.execute.return_value = alloc_res

    # Calculate expected costs dynamically:
    hr_working = await get_tool_hourly_rate(1760.0, mock_db, allocation_basis="working_day")
    hr_week = await get_tool_hourly_rate(1733.33 * 2, mock_db, allocation_basis="week")
    cal_cost = (304.167 / 30.4167) * 10
    month_cost = 500.0 * (15 / 30.4167)
    expected_total = round((hr_working * 20.0) + (hr_week * 20.0) + cal_cost + month_cost, 2)

    total_cost = await engine.calculate_tool_cost_for_milestone(milestone_id=1, milestone_hours_logged=20.0)
    assert total_cost == expected_total
    assert total_cost > 0.0


def test_update_project_admin_omitted_budget_preserves_existing():
    """Bug #13: When Admin updates project without budget in payload, existing budget is preserved."""
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Renamed Without Budget Field",
    }
    existing_project = MockProject(budget=50000.0)
    updated_project = MockProject(budget=50000.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=existing_project), \
         patch("app.modules.projects.service.ProjectRepository.update", return_value=updated_project) as mock_update, \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=50000.0)]):

        response = client.put("/api/v1/projects/1", json=payload, headers=admin_auth_headers())
        assert response.status_code == 200
        # In Pydantic update_data exclude_unset=True will omit budget, preserving existing DB value
        call_args = mock_update.call_args[0]
        project_in = call_args[1]
        dumped = project_in.model_dump(exclude_unset=True)
        assert "budget" not in dumped


def test_update_project_admin_explicit_null_budget():
    """Bug #13: When Admin explicitly sets budget to null, it is cleared."""
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Explicit Null Budget",
        "budget": None,
    }
    existing_project = MockProject(budget=50000.0)
    updated_project = MockProject(budget=None)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.service.ProjectRepository.get_by_id", return_value=existing_project), \
         patch("app.modules.projects.service.ProjectRepository.update", return_value=updated_project) as mock_update, \
         patch("app.modules.projects.service.ProjectService.compute_financials_for_projects", new_callable=AsyncMock, return_value=[MockProject(budget=None)]):

        response = client.put("/api/v1/projects/1", json=payload, headers=admin_auth_headers())
        assert response.status_code == 200
        call_args = mock_update.call_args[0]
        project_in = call_args[1]
        dumped = project_in.model_dump(exclude_unset=True)
        assert "budget" in dumped
        assert dumped["budget"] is None


def test_projects_unauthorized_role_forbidden():
    """Bug #13: Non-authorized roles (Employee) cannot create or update projects (403 Forbidden)."""
    emp_user = MockUser(id=50, role_name="Employee")
    token = create_access_token(data={"sub": "50"})
    emp_headers = {"Authorization": f"Bearer {token}"}

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=emp_user):
        create_res = client.post("/api/v1/projects/", json={"client_id": 1, "project_manager_id": 1, "project_name": "Test"}, headers=emp_headers)
        assert create_res.status_code == 403

        update_res = client.put("/api/v1/projects/1", json={"project_name": "Test"}, headers=emp_headers)
        assert update_res.status_code == 403


@pytest.mark.asyncio
async def test_financial_engine_ctc_scenarios_missing_null_zero_valid():
    """Bug #48: Test missing, null, zero, negative, and valid CTC scenarios."""
    from app.common.working_days_calculator import get_hourly_cost, DEFAULT_HOURLY_RATE
    mock_db = AsyncMock()

    # 1. Null / None CTC -> fallback rate
    rate_none = await get_hourly_cost(None, mock_db)
    assert rate_none == DEFAULT_HOURLY_RATE

    # 2. Zero CTC -> fallback rate
    rate_zero = await get_hourly_cost(0.0, mock_db)
    assert rate_zero == DEFAULT_HOURLY_RATE

    # 3. Negative CTC -> fallback rate
    rate_neg = await get_hourly_cost(-50000.0, mock_db)
    assert rate_neg == DEFAULT_HOURLY_RATE

    # 4. Valid CTC (e.g. 1,056,000 / ~2112 working hours ≈ 500.0) -> calculated rate
    exec_res = MagicMock()
    exec_res.scalars.return_value.first.return_value = None  # Uses default working calendar
    mock_db.execute.return_value = exec_res

    rate_valid = await get_hourly_cost(1056000.0, mock_db)
    assert rate_valid > 0.0
    assert isinstance(rate_valid, float)


@pytest.mark.asyncio
async def test_tool_cost_seat_multiplication_and_missing_dates():
    """Bug #51: Test seat multiplication, missing deallocation date bounding with cost_end_date."""
    from datetime import date
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    # Tool allocation with 3 seats, month basis, missing deallocation date
    ta = MagicMock()
    ta.monthly_cost = 1000.0
    ta.seats = 3
    ta.allocation_basis = "month"
    ta.status = "Active"
    ta.allocation_date = date(2026, 8, 1)
    ta.deallocation_date = None  # Missing deallocation date

    alloc_res = MagicMock()
    alloc_res.scalars.return_value.all.return_value = [ta]
    mock_db.execute.return_value = alloc_res

    # When cost_end_date is date(2026, 8, 31) (31 days)
    # Total monthly cost = 1000 * 3 = 3000
    # Pro-rated = 3000 * (31 / 30.4167) ≈ 3057.53
    cost = await engine.calculate_tool_cost_for_milestone(
        milestone_id=1, milestone_hours_logged=0.0, cost_end_date=date(2026, 8, 31)
    )
    expected = round((1000.0 * 3) * (31 / 30.4167), 2)
    assert cost == expected


@pytest.mark.asyncio
async def test_tool_cost_subscription_not_double_counted_with_logged_hours():
    """Bug #51: Verify subscription tools do not increase with logged hours."""
    from datetime import date
    mock_db = AsyncMock()
    engine = FinancialEngine(mock_db)

    ta = MagicMock()
    ta.monthly_cost = 600.0
    ta.seats = 1
    ta.allocation_basis = "calendar_day"
    ta.status = "Active"
    ta.allocation_date = date(2026, 9, 1)
    ta.deallocation_date = date(2026, 9, 30)  # 30 days

    alloc_res = MagicMock()
    alloc_res.scalars.return_value.all.return_value = [ta]
    mock_db.execute.return_value = alloc_res

    cost_0h = await engine.calculate_tool_cost_for_milestone(milestone_id=1, milestone_hours_logged=0.0)
    cost_100h = await engine.calculate_tool_cost_for_milestone(milestone_id=1, milestone_hours_logged=100.0)

    # Subscription cost must be identical regardless of whether 0 hours or 100 hours were logged
    assert cost_0h == cost_100h
    assert cost_0h == round((600.0 / 30.4167) * 30, 2)


