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

class MockTimesheet:
    def __init__(self, billable_hours=6.0, non_billable_hours=2.0):
        self.billable_hours = billable_hours
        self.non_billable_hours = non_billable_hours

    @property
    def hours(self) -> float:
        return (self.billable_hours or 0.0) + (self.non_billable_hours or 0.0)

    @property
    def is_billable(self) -> bool:
        return (self.billable_hours or 0.0) > 0.0

def test_dashboard_summary_success():
    user = MockUser(id=1, role_name="Employee")
    ts_list = [
        MockTimesheet(billable_hours=6.0, non_billable_hours=2.0),
        MockTimesheet(billable_hours=4.0, non_billable_hours=1.0),
    ]

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=user), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_entries_in_range", return_value=ts_list), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_by_user", return_value=[]), \
         patch("app.modules.leave_balances.repository.LeaveBalanceRepository.get_by_user_and_year", return_value=[]), \
         patch("app.modules.leave_requests.repository.LeaveRequestRepository.list_by_user", return_value=([], 0)):

        token = create_access_token(data={"sub": "1"})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/dashboard/summary", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert "timesheet_summary" in data
        ts = data["timesheet_summary"]
        assert ts["billable_hours"] == 10.0
        assert ts["non_billable_hours"] == 3.0
        assert ts["total_logged_hours"] == 13.0
