from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.reports.schema import LeaveReportItem, TimesheetReportItem

client = TestClient(app)


class MockRole:
    def __init__(self, id=1, name="Admin"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, role_name="Admin", status="Active"):
        self.id = id
        self.first_name = "Admin"
        self.last_name = "User"
        self.email = "admin@test.com"
        self.employee_id = "EMP001"
        self.status = status
        self.role = MockRole(id=1 if role_name == "Admin" else 2, name=role_name)


ADMIN_USER = MockUser(id=1, role_name="Admin")
PM_USER = MockUser(id=2, role_name="Project_Manager")


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def pm_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test: GET /api/v1/reports/timesheets
# ---------------------------------------------------------------------------

def test_get_timesheet_report_success():
    items = [
        TimesheetReportItem(
            timesheet_id=1,
            timesheet_date=date(2026, 8, 10),
            hours=8.0,
            is_billable=True,
            work_summary="Development work",
            user_id=1,
            user_name="John Doe",
            project_id=10,
            project_name="E-Commerce",
            client_id=5,
            client_name="Acme Corp",
        )
    ]

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.reports.service.ReportRepository.get_timesheet_report_data", return_value=items):

        response = client.get("/api/v1/reports/timesheets", headers=admin_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_hours"] == 8.0
        assert data["data"]["billable_hours"] == 8.0
        assert data["data"]["total_entries"] == 1


# ---------------------------------------------------------------------------
# Test: GET /api/v1/reports/leaves
# ---------------------------------------------------------------------------

def test_get_leave_report_success():
    items = [
        LeaveReportItem(
            leave_request_id=1,
            user_id=1,
            user_name="John Doe",
            leave_type_name="Paid Leave",
            start_date=date(2026, 8, 17),
            end_date=date(2026, 8, 19),
            status="Approved",
            reason="Vacation",
        )
    ]

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.reports.service.ReportRepository.get_leave_report_data", return_value=items):

        response = client.get("/api/v1/reports/leaves", headers=admin_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_requests"] == 1
        assert data["data"]["approved_requests"] == 1
