import pytest
from datetime import date
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.services.eod_report_service import EodReportService

client = TestClient(app)


class MockRole:
    def __init__(self, id=2, name="Project_Manager"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=2, role_name="Project_Manager", status="Active"):
        self.id = id
        self.first_name = "Alex"
        self.last_name = "PM"
        self.email = "alex.pm@company.com"
        self.employee_id = "EMP002"
        self.status = status
        self.role = MockRole(id=2 if role_name == "Project_Manager" else 3, name=role_name)


PM_USER = MockUser(id=2, role_name="Project_Manager")
EMPLOYEE_USER = MockUser(id=3, role_name="Employee")


def pm_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


def employee_headers():
    token = create_access_token(data={"sub": "3"})
    return {"Authorization": f"Bearer {token}"}


MOCK_ENTRIES = [
    {
        "timesheet_id": 101,
        "date": "2026-09-22",
        "employee_id": 11,
        "employee_name": "Alice Smith",
        "employee_email": "alice@company.com",
        "department": "Engineering",
        "project_id": 5,
        "project_name": "durrani",
        "project_code": "PRJ-5",
        "billable_hours": 6.5,
        "billable_work_summary": "Implemented authentication flow and user permissions",
        "non_billable_hours": 1.5,
        "non_billable_work_summary": "Daily standup meeting and sprint grooming",
        "total_hours": 8.0,
        "status": "submitted",
        "submitted_at": "2026-09-22 17:30:00",
    },
    {
        "timesheet_id": 102,
        "date": "2026-09-22",
        "employee_id": 12,
        "employee_name": "Bob Jones",
        "employee_email": "bob@company.com",
        "department": "Quality Assurance",
        "project_id": 5,
        "project_name": "durrani",
        "project_code": "PRJ-5",
        "billable_hours": 8.0,
        "billable_work_summary": "Created automated test suites for payment checkout",
        "non_billable_hours": 0.0,
        "non_billable_work_summary": "",
        "total_hours": 8.0,
        "status": "submitted",
        "submitted_at": "2026-09-22 17:45:00",
    },
]


def test_excel_generator():
    """Verify Excel workbook is correctly generated with proper headers and data."""
    target_date = date(2026, 9, 22)
    excel_bytes = EodReportService.generate_daily_eod_excel(MOCK_ENTRIES, target_date)
    assert excel_bytes is not None
    assert len(excel_bytes) > 0
    assert excel_bytes[:4] == b"PK\x03\x04"  # Zip/XLSX header signature


def test_csv_generator():
    """Verify CSV is correctly generated."""
    target_date = date(2026, 9, 22)
    csv_str = EodReportService.generate_daily_eod_csv(MOCK_ENTRIES, target_date)
    assert "Alice Smith" in csv_str
    assert "Bob Jones" in csv_str
    assert "Implemented authentication flow" in csv_str
    assert "Daily standup meeting" in csv_str


def test_get_daily_eod_preview_pm_success():
    """Verify PM can access daily EOD preview."""
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.services.eod_report_service.EodReportService.get_daily_eod_entries", new=AsyncMock(return_value=MOCK_ENTRIES)):
        response = client.get(
            "/api/v1/reports/daily-eod/preview?date=2026-09-22",
            headers=pm_headers(),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["date"] == "2026-09-22"
        assert data["total_submissions"] == 2
        assert data["total_employees"] == 2
        assert data["total_billable_hours"] == 14.5
        assert data["total_non_billable_hours"] == 1.5
        assert data["grand_total_hours"] == 16.0
        assert len(data["entries"]) == 2


def test_get_daily_eod_preview_forbidden_for_employee():
    """Verify standard Employee cannot access daily EOD preview."""
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.get(
            "/api/v1/reports/daily-eod/preview?date=2026-09-22",
            headers=employee_headers(),
        )
        assert response.status_code == 403


def test_export_daily_eod_xlsx_pm_success():
    """Verify PM can export daily EOD report as Excel."""
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.services.eod_report_service.EodReportService.get_daily_eod_entries", new=AsyncMock(return_value=MOCK_ENTRIES)):
        response = client.get(
            "/api/v1/reports/daily-eod/export?date=2026-09-22&format=xlsx",
            headers=pm_headers(),
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment; filename=daily_eod_report_20260922.xlsx" in response.headers["content-disposition"]
        assert len(response.content) > 0


def test_export_daily_eod_csv_pm_success():
    """Verify PM can export daily EOD report as CSV."""
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.services.eod_report_service.EodReportService.get_daily_eod_entries", new=AsyncMock(return_value=MOCK_ENTRIES)):
        response = client.get(
            "/api/v1/reports/daily-eod/export?date=2026-09-22&format=csv",
            headers=pm_headers(),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment; filename=daily_eod_report_20260922.csv" in response.headers["content-disposition"]
        assert b"Alice Smith" in response.content


def test_notify_slack_daily_eod_pm_success():
    """Verify PM can trigger sending daily EOD report to Slack."""
    mock_slack_res = {"ok": True, "message": "Daily EOD report uploaded successfully to Slack."}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.services.eod_report_service.EodReportService.send_daily_eod_to_slack", new=AsyncMock(return_value=mock_slack_res)):
        response = client.post(
            "/api/v1/reports/daily-eod/slack-notify?date=2026-09-22",
            headers=pm_headers(),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["ok"] is True
        assert "Slack" in data["message"]


@pytest.mark.asyncio
async def test_dispatch_daily_eod_report_with_entries():
    """Verify scheduled daily job dispatches to Slack when timesheets exist."""
    from app.scheduler.daily_eod_slack_job import dispatch_daily_eod_report

    mock_entries = [{"employee_id": 1, "employee_name": "Alice"}]
    mock_slack_res = {"ok": True, "message": "Report sent"}

    with patch("app.services.eod_report_service.EodReportService.get_daily_eod_entries", new=AsyncMock(return_value=mock_entries)), \
         patch("app.services.eod_report_service.EodReportService.send_daily_eod_to_slack", new=AsyncMock(return_value=mock_slack_res)):
        res = await dispatch_daily_eod_report()
        assert res["ok"] is True
        assert res["message"] == "Report sent"


@pytest.mark.asyncio
async def test_dispatch_daily_eod_report_no_entries_skips():
    """Verify scheduled daily job cleanly skips Slack dispatch when no timesheets exist."""
    from app.scheduler.daily_eod_slack_job import dispatch_daily_eod_report

    with patch("app.services.eod_report_service.EodReportService.get_daily_eod_entries", new=AsyncMock(return_value=[])):
        res = await dispatch_daily_eod_report()
        assert res["ok"] is True
        assert res.get("skipped") is True
        assert "No submissions" in res.get("reason", "")


