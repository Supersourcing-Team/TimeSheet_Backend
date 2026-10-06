from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.keka.leave_service import KekaLeaveService
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.leave_requests.model import LeaveRequest
from app.modules.leave_requests.repository import LeaveRequestRepository
from app.modules.leave_types.model import LeaveType
from app.modules.roles.model import Role
from app.modules.users.model import User
from app.services.keka.keka_auth import KekaAuthManager
from app.services.keka.keka_client import KekaAPIError, KekaClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_test_user(id=1, email="admin@test.com", employee_id="EMP001", role_name="Admin"):
    u = User(
        id=id,
        email=email,
        employee_id=employee_id,
        first_name="Test",
        last_name="User",
        role_id=1,
        status="Active",
    )
    u.role = Role(id=1, name=role_name)
    return u


ADMIN_USER = make_test_user(id=1, email="admin@test.com", role_name="Admin")
EMPLOYEE_USER = make_test_user(id=2, email="user@test.com", role_name="Employee")


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def employee_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


def make_test_leave_request(
    id=10,
    user_id=1,
    leave_type_id=1,
    start_date=date(2026, 10, 1),
    end_date=date(2026, 10, 2),
    reason="Medical Leave",
    status="Approved",
    leave_duration_type="full_day",
):
    leave = LeaveRequest(
        id=id,
        user_id=user_id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=status,
        leave_duration_type=leave_duration_type,
        created_at=datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
    )
    leave.user = ADMIN_USER
    leave.leave_type = LeaveType(id=1, name="Sick Leave", code="SL", days_per_year=12, is_paid=True, is_active=True)
    return leave


# ---------------------------------------------------------------------------
# 1. KekaClient create_leave_request Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keka_client_create_leave_request_success():
    mock_response = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"succeeded": True, "data": "keka-req-guid-123", "message": "Created"}),
    )

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_request:

        res = await KekaClient.create_leave_request(
            employee_id="keka-emp-uuid",
            from_date="2026-10-01T00:00:00Z",
            to_date="2026-10-02T00:00:00Z",
            leave_type_id="keka-leave-type-uuid",
            reason="Vacation",
        )

        assert res["succeeded"] is True
        assert res["data"] == "keka-req-guid-123"
        assert mock_request.called
        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert "/time/leaverequests" in call_kwargs["url"]
        assert call_kwargs["json"]["employeeId"] == "keka-emp-uuid"
        assert call_kwargs["json"]["leaveTypeId"] == "keka-leave-type-uuid"


@pytest.mark.asyncio
async def test_keka_client_create_leave_401_retry():
    resp_401 = MagicMock(status_code=401, text="Unauthorized")
    resp_200 = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"succeeded": True, "data": "keka-guid-after-refresh"}),
    )

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, side_effect=["old_tok", "new_tok"]) as mock_auth, \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=[resp_401, resp_200]):

        res = await KekaClient.create_leave_request(
            employee_id="keka-emp-uuid",
            from_date="2026-10-01T00:00:00Z",
            to_date="2026-10-02T00:00:00Z",
            leave_type_id="keka-leave-type-uuid",
            reason="Doctor Visit",
        )

        assert res["succeeded"] is True
        assert res["data"] == "keka-guid-after-refresh"
        assert mock_auth.call_count == 2


@pytest.mark.asyncio
async def test_keka_client_create_leave_429_rate_limit():
    resp_429 = MagicMock(status_code=429, text="Too Many Requests")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_429):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.create_leave_request(
                employee_id="keka-emp-uuid",
                from_date="2026-10-01T00:00:00Z",
                to_date="2026-10-02T00:00:00Z",
                leave_type_id="keka-leave-type-uuid",
                reason="Doctor Visit",
            )

        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_keka_client_create_leave_500_error():
    resp_500 = MagicMock(status_code=500, text="Internal Server Error")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_500):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.create_leave_request(
                employee_id="keka-emp-uuid",
                from_date="2026-10-01T00:00:00Z",
                to_date="2026-10-02T00:00:00Z",
                leave_type_id="keka-leave-type-uuid",
                reason="Doctor Visit",
            )

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# 2. KekaLeaveService Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keka_leave_service_successful_sync():
    leave = make_test_leave_request()
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-uuid-1"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": "keka-req-777"}):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        assert result["synced"] is True
        assert result["keka_leave_request_id"] == "keka-req-777"
        assert leave.synced_to_keka is True
        assert leave.keka_leave_request_id == "keka-req-777"
        assert leave.last_sync_error is None
        assert leave.last_synced_at is not None
        assert leave.status == "Approved"  # Local status is unchanged
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_keka_leave_service_missing_mapping():
    leave = make_test_leave_request()
    mock_db = AsyncMock()

    with patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=None):
        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert leave.synced_to_keka is False
        assert leave.keka_leave_request_id is None
        assert "no keka employee mapping found" in leave.last_sync_error.lower()
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_keka_leave_service_api_error_updates_error_field():
    leave = make_test_leave_request()
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-uuid-1"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, side_effect=KekaAPIError("Insufficient leave balance", status_code=400)):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert leave.synced_to_keka is False
        assert "insufficient leave balance" in leave.last_sync_error.lower()
        assert mock_db.commit.called


# ---------------------------------------------------------------------------
# 3. HTTP Endpoints Tests
# ---------------------------------------------------------------------------

def test_endpoint_get_leave_sync_status_admin():
    leave = make_test_leave_request()
    leave.synced_to_keka = True
    leave.keka_leave_request_id = "keka-req-999"

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=leave):

        response = client.get("/api/v1/keka/leave-requests/10/sync-status", headers=admin_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["local_leave_id"] == 10
        assert json_data["data"]["synced_to_keka"] is True
        assert json_data["data"]["keka_leave_request_id"] == "keka-req-999"


def test_endpoint_get_leave_sync_status_not_found():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=None):

        response = client.get("/api/v1/keka/leave-requests/9999/sync-status", headers=admin_headers())
        assert response.status_code == 404
        assert "not found" in response.text.lower()


def test_endpoint_sync_leave_action_admin():
    leave = make_test_leave_request()
    sync_result = {
        "success": True,
        "synced": True,
        "local_leave_id": 10,
        "keka_leave_request_id": "keka-req-manual-1",
        "last_synced_at": datetime.now(timezone.utc),
        "error": None,
        "message": "Leave request created successfully in Keka.",
    }

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=leave), \
         patch.object(KekaLeaveService, "sync_leave_to_keka", new_callable=AsyncMock, return_value=sync_result):

        response = client.post("/api/v1/keka/leave-requests/10/sync", headers=admin_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["synced"] is True
        assert json_data["data"]["keka_leave_request_id"] == "keka-req-manual-1"


def test_leave_endpoints_forbidden_for_non_admin():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        r1 = client.get("/api/v1/keka/leave-requests/10/sync-status", headers=employee_headers())
        assert r1.status_code == 403

        r2 = client.post("/api/v1/keka/leave-requests/10/sync", headers=employee_headers())
        assert r2.status_code == 403


def test_leave_sync_does_not_leak_secrets():
    leave = make_test_leave_request()
    sync_result = {
        "success": False,
        "synced": False,
        "local_leave_id": 10,
        "keka_leave_request_id": None,
        "error": "HTTP 401: Unauthorized",
        "message": "Failed to push leave to Keka",
    }

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=leave), \
         patch.object(KekaLeaveService, "sync_leave_to_keka", new_callable=AsyncMock, return_value=sync_result):

        response = client.post("/api/v1/keka/leave-requests/10/sync", headers=admin_headers())
        assert response.status_code == 200
        body_text = response.text.lower()
        assert "client_secret" not in body_text
        assert "api_key" not in body_text
        assert "access_token" not in body_text


@pytest.mark.asyncio
async def test_local_leave_submission_unaffected_when_keka_sync_fails():
    from app.modules.leave_requests.schema import LeaveRequestSubmit
    from app.modules.leave_requests.service import LeaveRequestService
    from app.modules.leave_types.model import LeaveType
    from app.modules.leave_types.repository import LeaveTypeRepository
    from app.modules.leave_requests.validator import LeaveRequestValidator

    mock_db = AsyncMock()
    user = make_test_user(id=5, email="emp@test.com")
    leave_type = LeaveType(id=2, name="Casual Leave", code="CL", is_active=True)
    req_input = LeaveRequestSubmit(
        leave_type_id=2,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 11),
        reason="Personal event",
    )

    fake_created = LeaveRequest(
        id=42,
        user_id=5,
        leave_type_id=2,
        start_date=req_input.start_date,
        end_date=req_input.end_date,
        reason=req_input.reason,
        status="Approved",
    )

    with patch.object(LeaveTypeRepository, "get_by_id", new_callable=AsyncMock, return_value=leave_type), \
         patch.object(LeaveRequestValidator, "calculate_working_days", new_callable=AsyncMock, return_value=2), \
         patch.object(LeaveRequestRepository, "create", new_callable=AsyncMock, return_value=fake_created), \
         patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaLeaveService, "sync_leave_to_keka", new_callable=AsyncMock, side_effect=Exception("Keka network outage")):

        res = await LeaveRequestService.submit_leave_request(mock_db, user, req_input)

        # Local leave record is successfully created despite Keka exception
        assert res is not None
        assert res.id == 42
        assert res.status == "Approved"
        assert res.reason == "Personal event"

