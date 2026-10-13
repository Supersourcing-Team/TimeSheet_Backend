from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token

client = TestClient(app)


class MockRole:
    def __init__(self, id=1, name="Admin"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, role_name="Admin", status="Active"):
        self.id = id
        self.first_name = "Test"
        self.last_name = "User"
        self.email = f"user{id}@test.com"
        self.employee_id = f"EMP00{id}"
        self.status = status
        self.role = MockRole(id=1 if role_name == "Admin" else 4, name=role_name)


class MockLeaveType:
    def __init__(self, id=1, name="Paid Leave", is_active=True):
        self.id = id
        self.name = name
        self.is_active = is_active


class MockLeaveBalance:
    def __init__(self, id=1, user_id=2, leave_type_id=1, year=2026, allocated_days=20, used_days=2):
        self.id = id
        self.user_id = user_id
        self.leave_type_id = leave_type_id
        self.year = year
        self.allocated_days = allocated_days
        self.used_days = used_days


class MockLeaveRequest:
    def __init__(self, id=1, user_id=2, leave_type_id=1, status="Pending", **kwargs):
        from datetime import datetime
        self.id = id
        self.user_id = user_id
        self.leave_type_id = leave_type_id
        self.start_date = kwargs.get("start_date", date(2026, 8, 17))
        self.end_date = kwargs.get("end_date", date(2026, 8, 19))
        self.reason = kwargs.get("reason", "Vacation")
        self.status = status
        self.managers_user_id = None
        self.rejection_reason = None
        self.created_at = datetime(2026, 8, 10)
        self.updated_at = datetime(2026, 8, 10)
        self.user = EMPLOYEE_USER
        self.leave_type = MockLeaveType()
        self.manager = None
        for k, v in kwargs.items():
            setattr(self, k, v)


ADMIN_USER = MockUser(id=1, role_name="Admin")
EMPLOYEE_USER = MockUser(id=2, role_name="Employee")


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def employee_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test: POST /api/v1/leave-requests
# ---------------------------------------------------------------------------

def test_submit_leave_request_success():
    payload = {
        "leave_type_id": 1,
        "start_date": "2026-08-17",
        "end_date": "2026-08-19",
        "reason": "Family trip",
    }
    leave_type = MockLeaveType()
    balance = MockLeaveBalance()
    created_req = MockLeaveRequest(id=10, user_id=2, status="Pending")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.leave_types.repository.LeaveTypeRepository.get_by_id", return_value=leave_type), \
         patch("app.modules.holidays.repository.HolidayRepository.get_all", return_value=[]), \
         patch("app.modules.leave_balances.repository.LeaveBalanceRepository.get_specific_balance", return_value=balance), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.create", return_value=created_req):

        response = client.post("/api/v1/leave-requests/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Pending"


def test_submit_leave_request_exceeds_balance():
    payload = {
        "leave_type_id": 1,
        "start_date": "2026-08-17",
        "end_date": "2026-08-28",  # 10 working days
        "reason": "Extended leave",
    }
    leave_type = MockLeaveType()
    balance = MockLeaveBalance(allocated_days=5, used_days=2)  # only 3 available

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.leave_types.repository.LeaveTypeRepository.get_by_id", return_value=leave_type), \
         patch("app.modules.holidays.repository.HolidayRepository.get_all", return_value=[]), \
         patch("app.modules.leave_balances.repository.LeaveBalanceRepository.get_specific_balance", return_value=balance):

        response = client.post("/api/v1/leave-requests/", json=payload, headers=employee_headers())
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "Insufficient leave balance" in data["message"]


# ---------------------------------------------------------------------------
# Test: PUT /api/v1/leave-requests/{id}/approve
# ---------------------------------------------------------------------------

def test_approve_leave_request_success():
    req = MockLeaveRequest(id=1, user_id=2, status="Pending")
    balance = MockLeaveBalance()
    approved_req = MockLeaveRequest(id=1, user_id=2, status="Approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=req), \
         patch("app.modules.holidays.repository.HolidayRepository.get_all", return_value=[]), \
         patch("app.modules.leave_balances.repository.LeaveBalanceRepository.get_specific_balance", return_value=balance), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.update_status", return_value=approved_req):

        response = client.put("/api/v1/leave-requests/1/approve", headers=admin_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Approved"


# ---------------------------------------------------------------------------
# Test: PUT /api/v1/leave-requests/{id}/reject
# ---------------------------------------------------------------------------

def test_reject_leave_request_success():
    req = MockLeaveRequest(id=1, user_id=2, status="Pending")
    rejected_req = MockLeaveRequest(id=1, user_id=2, status="Rejected")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=req), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.update_status", return_value=rejected_req):

        response = client.put(
            "/api/v1/leave-requests/1/reject",
            json={"rejection_reason": "High project workload"},
            headers=admin_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Rejected"


# ---------------------------------------------------------------------------
# Additional Lifecycle & Balance Accounting Tests for Bug #2
# ---------------------------------------------------------------------------

def test_approve_already_approved_leave_request_conflict():
    """Attempting to approve a leave that is already Approved returns 409 Conflict."""
    already_approved = MockLeaveRequest(id=1, user_id=2, status="Approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=already_approved):

        response = client.put("/api/v1/leave-requests/1/approve", headers=admin_headers())
        assert response.status_code == 409
        assert "Cannot approve leave request with status 'Approved'" in response.json()["message"]


def test_reject_already_approved_leave_request_conflict():
    """Attempting to reject a leave that is already Approved returns 409 Conflict."""
    already_approved = MockLeaveRequest(id=1, user_id=2, status="Approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=already_approved):

        response = client.put(
            "/api/v1/leave-requests/1/reject",
            json={"rejection_reason": "Changed mind"},
            headers=admin_headers(),
        )
        assert response.status_code == 409
        assert "Cannot reject leave request with status 'Approved'" in response.json()["message"]


def test_cancel_pending_leave_request_no_balance_change():
    """Cancelling a Pending leave request sets status to Cancelled without refunding balance."""
    req = MockLeaveRequest(id=1, user_id=2, status="Pending")
    cancelled_req = MockLeaveRequest(id=1, user_id=2, status="Cancelled")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=req), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.update_status", return_value=cancelled_req):

        response = client.delete("/api/v1/leave-requests/1/cancel", headers=employee_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Cancelled"


def test_cancel_already_cancelled_leave_conflict():
    """Cancelling an already cancelled leave raises 409 Conflict."""
    req = MockLeaveRequest(id=1, user_id=2, status="Cancelled")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.get_by_id", return_value=req):

        response = client.delete("/api/v1/leave-requests/1/cancel", headers=employee_headers())
        assert response.status_code == 409
        assert "Leave request is already cancelled" in response.json()["message"]


def test_mark_leave_from_timesheet_remains_auto_approved():
    """The separate mark-leave-from-timesheet endpoint creates auto-Approved records."""
    payload = {
        "leave_date": "2026-08-17",
        "leave_duration_type": "full_day",
        "leave_type_id": 1,
        "reason": "Doctor visit",
    }
    leave_type = MockLeaveType()
    created_rec = MockLeaveRequest(id=50, user_id=2, status="Approved", start_date=date(2026, 8, 17), end_date=date(2026, 8, 17))

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.leave_types.repository.LeaveTypeRepository.get_by_id", return_value=leave_type), \
         patch("app.modules.leave_requests.validator.LeaveRequestValidator.validate_no_duplicate_leave"), \
         patch("app.modules.leave_requests.validator.LeaveRequestValidator.validate_no_timesheet_conflict"), \
         patch("app.modules.leave_requests.service.LeaveRequestRepository.create", return_value=created_rec):

        response = client.post("/api/v1/leave-requests/mark-from-timesheet", json=payload, headers=employee_headers())
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "Approved"
