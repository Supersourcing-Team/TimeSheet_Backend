from datetime import date, datetime
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token

client = TestClient(app)


class MockRole:
    def __init__(self, id=4, name="Employee"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, role_name="Employee", status="Active"):
        self.id = id
        self.first_name = "Jane"
        self.last_name = "Doe"
        self.email = "jane@test.com"
        self.employee_id = "EMP001"
        self.status = status
        self.role = MockRole(name=role_name)


class MockProjectAssignment:
    def __init__(self, id=1, project_id=10, user_id=1, role="Developer", assignment_status="Active"):
        self.id = id
        self.project_id = project_id
        self.user_id = user_id
        self.role = role
        self.assignment_status = assignment_status


class MockTimesheet:
    def __init__(self, id=1, user_id=1, project_assignment_id=1, hours=7.5):
        self.id = id
        self.user_id = user_id
        self.project_assignment_id = project_assignment_id
        self.timesheet_date = date(2026, 8, 11)
        self.hours = hours
        self.is_billable = True
        self.task_description = "Feature development"
        self.work_summary = "Built timesheet modules"
        self.created_at = datetime(2026, 8, 11)
        self.updated_at = datetime(2026, 8, 11)
        self.project_assignment = MockProjectAssignment()


EMPLOYEE_USER = MockUser(id=1, role_name="Employee")


def employee_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test: POST /api/v1/timesheets
# ---------------------------------------------------------------------------

def test_create_timesheet_success():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "hours": 6.0,
        "is_billable": True,
        "work_summary": "Backend API development",
    }
    assignment = MockProjectAssignment()
    created_ts = MockTimesheet(id=1, user_id=1, hours=6.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select") as mock_select, \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.service.TimesheetRepository.create", return_value=created_ts):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["hours"] == 6.0


def test_create_timesheet_exceeds_daily_8h_limit():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "hours": 5.0,
        "work_summary": "Extra hours",
    }
    assignment = MockProjectAssignment()

    # Already logged 4.0h today -> 4.0 + 5.0 = 9.0 > 8.0 Max
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=4.0):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "Exceeds daily 8-hour max limit" in data["message"]


# ---------------------------------------------------------------------------
# Test: GET /api/v1/timesheets/weekly-summary
# ---------------------------------------------------------------------------

def test_get_weekly_summary_success():
    entry = MockTimesheet(id=1, hours=7.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_entries_in_range", return_value=[entry]):

        response = client.get("/api/v1/timesheets/weekly-summary?target_date=2026-08-11", headers=employee_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_weekly_hours"] == 7.0
        assert len(data["data"]["daily_breakdowns"]) == 7
