from datetime import date, datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest

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
    def __init__(self, id=1, project_id=10, user_id=1, role="Developer", assignment_status="Active", is_active=True):
        self.id = id
        self.project_id = project_id
        self.user_id = user_id
        self.role = role
        self.assignment_status = assignment_status
        self.is_active = is_active

class MockTimesheet:
    def __init__(
        self, 
        id=1, 
        user_id=1, 
        project_assignment_id=1, 
        billable_hours=0.0, 
        non_billable_hours=0.0,
        billable_work_summary=None,
        non_billable_work_summary=None,
        status="draft"
    ):
        self.id = id
        self.user_id = user_id
        self.project_assignment_id = project_assignment_id
        self.timesheet_date = date(2026, 8, 11)
        self.billable_hours = billable_hours
        self.non_billable_hours = non_billable_hours
        self.billable_work_summary = billable_work_summary
        self.non_billable_work_summary = non_billable_work_summary
        self.status = status
        self.created_at = datetime(2026, 8, 11)
        self.updated_at = datetime(2026, 8, 11)
        self.project_assignment = MockProjectAssignment()

EMPLOYEE_USER = MockUser(id=1, role_name="Employee")

def employee_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}

def test_billable_only():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 5.0,
        "billable_work_summary": "Billable API dev",
        "non_billable_hours": 0.0,
    }
    assignment = MockProjectAssignment()
    created_ts = MockTimesheet(id=1, billable_hours=5.0, billable_work_summary="Billable API dev")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=None), \
         patch("app.modules.timesheets.repository.TimesheetRepository.create", return_value=created_ts) as mock_create:

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["billable_hours"] == 5.0
        assert mock_create.called

def test_non_billable_only():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 0.0,
        "non_billable_hours": 3.0,
        "non_billable_work_summary": "Internal meeting",
    }
    assignment = MockProjectAssignment()
    created_ts = MockTimesheet(id=2, non_billable_hours=3.0, non_billable_work_summary="Internal meeting")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=None), \
         patch("app.modules.timesheets.repository.TimesheetRepository.create", return_value=created_ts):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201

def test_both_in_one_row():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 4.0,
        "non_billable_hours": 4.0,
    }
    assignment = MockProjectAssignment()
    created_ts = MockTimesheet(id=3, billable_hours=4.0, non_billable_hours=4.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=None), \
         patch("app.modules.timesheets.repository.TimesheetRepository.create", return_value=created_ts):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201

def test_create_then_update_true_upsert():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 5.0,
        "non_billable_hours": 2.0,
    }
    assignment = MockProjectAssignment()
    existing_ts = MockTimesheet(id=4, billable_hours=3.0, non_billable_hours=0.0)
    updated_ts = MockTimesheet(id=4, billable_hours=5.0, non_billable_hours=2.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=existing_ts), \
         patch("app.modules.timesheets.repository.TimesheetRepository.update", return_value=updated_ts) as mock_update, \
         patch("app.modules.timesheets.repository.TimesheetRepository.create") as mock_create:

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        assert mock_update.called
        assert not mock_create.called

def test_repeated_submission_does_not_duplicate():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 4.0,
    }
    assignment = MockProjectAssignment()
    existing_ts = MockTimesheet(id=5, billable_hours=4.0)
    updated_ts = MockTimesheet(id=5, billable_hours=4.0)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=existing_ts), \
         patch("app.modules.timesheets.repository.TimesheetRepository.update", return_value=updated_ts) as mock_update:

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        args = mock_update.call_args[0][2]
        assert args["billable_hours"] == 4.0

def test_exceeds_daily_limit_24h():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 20.0,
        "non_billable_hours": 5.0,
    }
    assignment = MockProjectAssignment()
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.select"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=None):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 400
        assert "Single entry cannot exceed 24.0 hours" in response.json()["message"]

def test_get_weekly_summary_success():
    entry = MockTimesheet(id=1, billable_hours=4.0, non_billable_hours=3.0)
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_entries_in_range", return_value=[entry]):

        response = client.get("/api/v1/timesheets/weekly-summary?target_date=2026-08-11", headers=employee_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_weekly_hours"] == 7.0

def pm_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}

PM_USER = MockUser(id=2, role_name="Project_Manager")

def test_pm_cannot_create_timesheet():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-11",
        "billable_hours": 4.0,
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.post("/api/v1/timesheets/", json=payload, headers=pm_headers())
        assert response.status_code == 403

def test_pm_cannot_update_timesheet():
    payload = {
        "billable_hours": 4.0,
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.put("/api/v1/timesheets/1", json=payload, headers=pm_headers())
        assert response.status_code == 403

def test_pm_cannot_delete_timesheet():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.delete("/api/v1/timesheets/1", headers=pm_headers())
        assert response.status_code == 403

def test_cannot_create_timesheet_future_date():
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2099-01-01",
        "billable_hours": 4.0,
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code in [400, 422]
        assert "Cannot log timesheets for future dates" in str(response.json())

def test_cannot_update_timesheet_future_date():
    payload = {
        "timesheet_date": "2099-01-01",
        "billable_hours": 4.0,
    }
    existing_ts = MockTimesheet(id=1)
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=existing_ts):
        response = client.put("/api/v1/timesheets/1", json=payload, headers=employee_headers())
        assert response.status_code in [400, 422]
        assert "Cannot log timesheets for future dates" in str(response.json())


