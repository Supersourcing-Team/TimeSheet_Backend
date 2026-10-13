from datetime import date, datetime
from unittest.mock import patch
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

@pytest.fixture(autouse=True)
def override_database():
    from app.core.database import get_db
    from unittest.mock import AsyncMock

    class MockScalars:
        def all(self):
            return []
        def first(self):
            return None

    class MockResult:
        def scalars(self):
            return MockScalars()
        def scalar_one_or_none(self):
            return None
        def scalar(self):
            return 0

    mock_db = AsyncMock()
    mock_db.execute.return_value = MockResult()

    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db
    with patch("app.modules.holidays.repository.HolidayRepository.get_by_date", return_value=None), \
         patch("app.modules.leave_requests.repository.LeaveRequestRepository.get_approved_leaves_for_date", return_value=[]):
        yield
    app.dependency_overrides.pop(get_db, None)

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
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=MockTimesheet(id=1, user_id=1)):
        response = client.put("/api/v1/timesheets/1", json=payload, headers=pm_headers())
        assert response.status_code == 403

def test_pm_cannot_delete_timesheet():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=MockTimesheet(id=1, user_id=1)):
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


# ---------------------------------------------------------------------------
# Bug #3: Timesheet Review (Approve/Reject) & Approved State Protections
# ---------------------------------------------------------------------------

class MockProject:
    def __init__(self, id=10, project_manager_id=2):
        self.id = id
        self.project_manager_id = project_manager_id

ADMIN_USER = MockUser(id=99, role_name="Admin")
def admin_headers():
    token = create_access_token(data={"sub": "99"})
    return {"Authorization": f"Bearer {token}"}

def make_reviewable_timesheet(pm_id=2, status="submitted"):
    ts = MockTimesheet(id=1, user_id=1, status=status)
    ts.project_assignment = MockProjectAssignment(id=1, project_id=10, user_id=1)
    ts.project_assignment.project = MockProject(id=10, project_manager_id=pm_id)
    return ts

def test_pm_approves_timesheet_success():
    """Authorized PM approves submitted timesheet for their managed project."""
    ts = make_reviewable_timesheet(pm_id=2, status="submitted")
    approved_ts = make_reviewable_timesheet(pm_id=2, status="approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_by_id", return_value=ts), \
         patch("app.modules.timesheets.service.TimesheetRepository.update", return_value=approved_ts):

        response = client.put("/api/v1/timesheets/1/approve", headers=pm_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "approved"

def test_admin_approves_timesheet_success():
    """Admin can approve timesheet across any project."""
    ts = make_reviewable_timesheet(pm_id=55, status="submitted")
    approved_ts = make_reviewable_timesheet(pm_id=55, status="approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_by_id", return_value=ts), \
         patch("app.modules.timesheets.service.TimesheetRepository.update", return_value=approved_ts):

        response = client.put("/api/v1/timesheets/1/approve", headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "approved"

def test_pm_rejects_timesheet_success():
    """Authorized PM rejects submitted timesheet for their managed project."""
    ts = make_reviewable_timesheet(pm_id=2, status="submitted")
    rejected_ts = make_reviewable_timesheet(pm_id=2, status="rejected")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_by_id", return_value=ts), \
         patch("app.modules.timesheets.service.TimesheetRepository.update", return_value=rejected_ts):

        response = client.put("/api/v1/timesheets/1/reject", headers=pm_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "rejected"

def test_pm_cannot_approve_timesheet_of_unmanaged_project():
    """PM cannot approve timesheet for project managed by a different PM."""
    ts = make_reviewable_timesheet(pm_id=88, status="submitted")  # Managed by user 88, not PM_USER (id 2)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_by_id", return_value=ts):

        response = client.put("/api/v1/timesheets/1/approve", headers=pm_headers())
        assert response.status_code == 403
        assert "Only the Project Manager assigned to this project" in response.json()["message"]

def test_employee_cannot_call_approve_or_reject():
    """Employees without PM/Admin roles cannot call approval or rejection endpoints."""
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        app_res = client.put("/api/v1/timesheets/1/approve", headers=employee_headers())
        assert app_res.status_code == 403

        rej_res = client.put("/api/v1/timesheets/1/reject", headers=employee_headers())
        assert rej_res.status_code == 403

def test_repeated_approval_or_rejection_conflict():
    """Timesheet already approved or rejected raises 409 Conflict."""
    already_approved = make_reviewable_timesheet(pm_id=2, status="approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.timesheets.service.TimesheetRepository.get_by_id", return_value=already_approved):

        res = client.put("/api/v1/timesheets/1/approve", headers=pm_headers())
        assert res.status_code == 409
        assert "Cannot approve timesheet with status 'approved'" in res.json()["message"]

def test_employee_cannot_update_approved_timesheet():
    """Employee cannot modify a timesheet that is already approved."""
    payload = {"billable_hours": 5.0}
    approved_ts = make_reviewable_timesheet(pm_id=2, status="approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=approved_ts):

        res = client.put("/api/v1/timesheets/1", json=payload, headers=employee_headers())
        assert res.status_code == 400
        assert "Approved timesheet entries cannot be modified" in res.json()["message"]

def test_employee_cannot_delete_approved_timesheet():
    """Employee cannot delete a timesheet that is already approved."""
    approved_ts = make_reviewable_timesheet(pm_id=2, status="approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=approved_ts):

        res = client.delete("/api/v1/timesheets/1", headers=employee_headers())
        assert res.status_code == 400
        assert "Approved timesheet entries cannot be deleted" in res.json()["message"]

def test_create_timesheet_weekend_without_approved_request():
    """Saturday submission without an approved request fails with 400."""
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-15",  # Saturday
        "billable_hours": 6.0,
        "billable_work_summary": "Weekend work",
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 400
        assert "weekends" in response.json()["message"].lower()

def test_create_timesheet_weekend_with_approved_request():
    """Saturday submission with an approved request succeeds with 201."""
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": "2026-08-15",  # Saturday
        "billable_hours": 6.0,
        "billable_work_summary": "Approved weekend work",
    }
    assignment = MockProjectAssignment()
    created_ts = MockTimesheet(id=99, billable_hours=6.0, billable_work_summary="Approved weekend work")
    created_ts.timesheet_date = date(2026, 8, 15)

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_not_weekend") as mock_weekend_val, \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_not_holiday"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_user_project_date", return_value=None), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_no_leave_conflict"), \
         patch("app.modules.timesheets.repository.TimesheetRepository.create", return_value=created_ts):

        response = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        mock_weekend_val.assert_called_once()

def test_update_timesheet_to_weekend_without_approved_request():
    """Updating timesheet date to weekend without approved request fails with 400."""
    initial_ts = MockTimesheet(id=1, status="submitted")
    initial_ts.timesheet_date = date(2026, 8, 11)  # Tuesday
    payload = {"timesheet_date": "2026-08-15"}  # Saturday

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=initial_ts):

        res = client.put("/api/v1/timesheets/1", json=payload, headers=employee_headers())
        assert res.status_code == 400
        assert "weekends" in res.json()["message"].lower()

def test_update_timesheet_to_weekend_with_approved_request():
    """Updating timesheet date to weekend with approved request succeeds."""
    initial_ts = MockTimesheet(id=1, status="submitted", billable_hours=4.0)
    initial_ts.timesheet_date = date(2026, 8, 11)
    updated_ts = MockTimesheet(id=1, status="submitted", billable_hours=4.0)
    updated_ts.timesheet_date = date(2026, 8, 15)
    payload = {"timesheet_date": "2026-08-15"}

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=initial_ts), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_not_weekend") as mock_weekend_val, \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_not_holiday"), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_daily_total_hours", return_value=0.0), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_no_leave_conflict"), \
         patch("app.modules.timesheets.repository.TimesheetRepository.update", return_value=updated_ts):

        res = client.put("/api/v1/timesheets/1", json=payload, headers=employee_headers())
        assert res.status_code == 200, res.json()
        mock_weekend_val.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 2 Targeted Tests: Bugs #9, #10, #16, #17, #20, #44
# ---------------------------------------------------------------------------

def test_timesheet_short_description_fails_validation():
    """Bug #20: Descriptions shorter than 3 characters fail validation."""
    payload = {
        "project_assignment_id": 1,
        "timesheet_date": str(date.today()),
        "billable_hours": 4.0,
        "billable_work_summary": "hi",  # Too short (< 3 chars)
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        res = client.post("/api/v1/timesheets/", json=payload, headers=employee_headers())
        assert res.status_code in (400, 422)


def test_batch_timesheet_atomicity_and_duplicate_detection():
    """Bug #10 & #19: Batch endpoint rejects duplicate rows in batch."""
    today_str = str(date.today())
    payload = [
        {
            "project_assignment_id": 1,
            "timesheet_date": today_str,
            "billable_hours": 3.0,
            "billable_work_summary": "Feature code",
        },
        {
            "project_assignment_id": 1,
            "timesheet_date": today_str,
            "billable_hours": 2.0,
            "billable_work_summary": "Duplicate entry",
        },
    ]
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        res = client.post("/api/v1/timesheets/batch", json=payload, headers=employee_headers())
        assert res.status_code in (400, 422)
        assert "duplicate" in res.json()["message"].lower() or "duplicate" in str(res.json()).lower()


def test_admin_can_update_approved_timesheet():
    """Bug #44: Admin can modify approved timesheet for correction, while normal employee cannot."""
    approved_ts = make_reviewable_timesheet(pm_id=2, status="approved")
    updated_ts = make_reviewable_timesheet(pm_id=2, status="approved")
    updated_ts.billable_hours = 6.0
    payload = {"billable_hours": 6.0}

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.timesheets.repository.TimesheetRepository.get_by_id", return_value=approved_ts), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_daily_hours"), \
         patch("app.modules.timesheets.validator.TimesheetValidator.validate_no_leave_conflict"), \
         patch("app.modules.timesheets.repository.TimesheetRepository.update", return_value=updated_ts):

        res = client.put("/api/v1/timesheets/1", json=payload, headers=admin_headers())
        assert res.status_code == 200
        assert res.json()["data"]["billable_hours"] == 6.0


@pytest.mark.asyncio
async def test_batch_timesheet_atomic_rollback_leaves_zero_persisted_rows():
    """
    Bug #10 Database-Backed Integration Test:
    Proves that if a batch timesheet submission fails after at least one row has been
    staged into the session, the transaction rollback leaves ZERO persisted rows in the database.
    Also verifies that a completely valid batch persists all expected rows.
    Uses an isolated in-memory SQLite database with real SQLAlchemy async sessions.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import select, event
    import app.core.models
    from app.core.database import Base
    from app.modules.roles.model import Role
    from app.modules.users.model import User
    from app.modules.clients.model import Client
    from app.modules.projects.model import Project
    from app.modules.project_assignments.model import ProjectAssignment
    from app.modules.timesheets.model import Timesheet
    from app.modules.timesheets.schema import TimesheetCreate
    from app.modules.timesheets.service import TimesheetService
    from app.core.exceptions import BadRequestException, ForbiddenException

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed test data in real database
    async with async_session() as session:
        role = Role(id=1, name="Employee")
        session.add(role)
        user = User(
            id=10,
            email="batch_test@example.com",
            first_name="Alice",
            last_name="Tester",
            role_id=1,
            employee_id="EMP_BATCH_10",
            status="Active",
        )
        session.add(user)
        client = Client(id=1, name="Batch Client")
        session.add(client)
        project1 = Project(id=1, project_name="Batch Project 1", client_id=1, project_manager_id=10, is_active=True)
        project2 = Project(id=2, project_name="Batch Project 2", client_id=1, project_manager_id=10, is_active=True)
        session.add_all([project1, project2])
        assignment1 = ProjectAssignment(
            id=101,
            project_id=1,
            user_id=10,
            is_active=True,
        )
        assignment2 = ProjectAssignment(
            id=102,
            project_id=2,
            user_id=10,
            is_active=True,
        )
        session.add_all([assignment1, assignment2])
        await session.commit()

    # Step 1: Batch where Row 1 is valid (and staged) and Row 2 fails
    valid_date = date(2026, 9, 16)  # Wednesday (weekday, non-future)
    row1 = TimesheetCreate(
        project_assignment_id=101,
        timesheet_date=valid_date,
        billable_hours=4.0,
        billable_work_summary="Task 1 implementation",
    )
    row2_invalid = TimesheetCreate(
        project_assignment_id=999,  # Non-existent assignment -> raises ForbiddenException during loop after row1 is staged
        timesheet_date=valid_date,
        billable_hours=4.0,
        billable_work_summary="Task 2 implementation",
    )

    staged_timesheet_assignments = []
    async with async_session() as session:
        @event.listens_for(session.sync_session, "before_flush")
        def capture_before_flush(sess, flush_context, instances):
            for obj in sess.new:
                if isinstance(obj, Timesheet):
                    staged_timesheet_assignments.append(obj.project_assignment_id)

        user_obj = await session.get(User, 10)
        with pytest.raises((BadRequestException, ForbiddenException)):
            await TimesheetService.create_timesheets_batch(
                db=session,
                current_user=user_obj,
                batch_in=[row1, row2_invalid],
            )

        # Explicitly confirm that row 1 was staged into session.new and reached the flush pipeline before row 2 failed
        assert 101 in staged_timesheet_assignments, (
            f"Expected row 1 (assignment 101) to be staged before row 2 failure, but got: {staged_timesheet_assignments}"
        )

    # Step 2: Verify through a fresh database query that ZERO rows from the failed batch remain persisted
    async with async_session() as fresh_session:
        result = await fresh_session.execute(select(Timesheet).where(Timesheet.user_id == 10))
        persisted_rows = result.scalars().all()
        assert len(persisted_rows) == 0, f"Expected 0 persisted rows after rollback, but found {len(persisted_rows)}"

    # Step 3: Verify that a completely valid batch persists all expected rows
    row2_valid = TimesheetCreate(
        project_assignment_id=102,
        timesheet_date=valid_date,
        billable_hours=3.5,
        billable_work_summary="Task 2 valid implementation",
    )

    async with async_session() as session:
        user_obj = await session.get(User, 10)
        created_timesheets = await TimesheetService.create_timesheets_batch(
            db=session,
            current_user=user_obj,
            batch_in=[row1, row2_valid],
        )
        assert len(created_timesheets) == 2

    # Step 4: Verify through a fresh database query that both rows are persisted
    async with async_session() as fresh_session:
        result = await fresh_session.execute(select(Timesheet).where(Timesheet.user_id == 10))
        persisted_valid_rows = result.scalars().all()
        assert len(persisted_valid_rows) == 2
        saved_assignments = {ts.project_assignment_id for ts in persisted_valid_rows}
        assert saved_assignments == {101, 102}
        total_hours = sum(ts.billable_hours for ts in persisted_valid_rows)
        assert total_hours == 7.5

    await engine.dispose()





