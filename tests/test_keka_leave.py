from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.keka.leave_service import KekaLeaveService
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.leave_requests.model import LeaveRequest
from app.modules.leave_requests.repository import LeaveRequestRepository
from app.modules.leave_types.model import LeaveType
from app.modules.leave_types.repository import LeaveTypeRepository
from app.modules.leave_balances.repository import LeaveBalanceRepository
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
    half_day_period=None,
    keka_leave_type_id="keka-lt-uuid-1",
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
        half_day_period=half_day_period,
        created_at=datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
    )
    leave.user = ADMIN_USER
    leave.leave_type = LeaveType(
        id=1,
        name="Sick Leave",
        code="SL",
        days_per_year=12,
        is_paid=True,
        is_active=True,
        keka_leave_type_id=keka_leave_type_id,
    )
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
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": "c62391b1-218f-410a-b286-6eb452b12345"}):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        assert result["synced"] is True
        assert result["keka_leave_request_id"] == "c62391b1-218f-410a-b286-6eb452b12345"
        assert leave.synced_to_keka is True
        assert leave.keka_leave_request_id == "c62391b1-218f-410a-b286-6eb452b12345"
        assert leave.last_sync_error is None
        assert leave.last_synced_at is not None
        assert leave.status == "Approved"
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
        status="Pending",
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
        assert res.status == "Pending"
        assert res.reason == "Personal event"


# ---------------------------------------------------------------------------
# Phase 3: Authoritative Keka Leave Balances Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leave_balances_live_keka_mapped_employee():
    """Mapped employee with configured Keka fetches authoritative live balances from Keka."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 7
    mapping = KekaEmployeeMapping(id=1, local_user_id=user_id, keka_employee_id="keka-uuid-7")

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "keka-uuid-7",
                "employeeNumber": "EMP007",
                "employeeName": "Test Employee",
                "leaveBalance": [
                    {
                        "leaveTypeId": "keka-lt-casual-uuid",
                        "leaveTypeName": "Casual Leave",
                        "availableBalance": 14.5,
                        "used": 3.5,
                        "annualQuota": 18.0,
                        "accrued": 15.0,
                    },
                    {
                        "leaveTypeId": "keka-lt-sick-uuid",
                        "leaveTypeName": "Sick Leave",
                        "availableBalance": 10.0,
                        "used": 2.0,
                        "annualQuota": 12.0,
                        "accrued": 12.0,
                    },
                ],
            }
        ],
    }

    local_lt1 = LeaveType(id=1, name="Casual Leave", code="CL", keka_leave_type_id="keka-lt-casual-uuid", is_active=True)
    local_lt2 = LeaveType(id=2, name="Sick Leave", code="SL", keka_leave_type_id="keka-lt-sick-uuid", is_active=True)

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt1, local_lt2]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 2
        # First balance: Casual Leave
        b1 = balances[0]
        assert b1.leave_type_name == "Casual Leave"
        assert b1.available_balance == 14.5
        assert b1.used_days == 3.5
        assert b1.annual_quota == 18.0
        assert b1.accrued_days == 15.0
        assert b1.remaining_days == 14.5
        assert b1.source == "keka"
        assert b1.is_live is True
        assert b1.sync_error is None
        assert b1.keka_leave_type_id == "keka-lt-casual-uuid"

        # Second balance: Sick Leave
        b2 = balances[1]
        assert b2.leave_type_name == "Sick Leave"
        assert b2.available_balance == 10.0
        assert b2.used_days == 2.0
        assert b2.annual_quota == 12.0
        assert b2.source == "keka"
        assert b2.is_live is True


@pytest.mark.asyncio
async def test_leave_balances_unmapped_employee_returns_local():
    """Unmapped employee falls back to local balances cleanly with source='local' and is_live=False."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.leave_balances.model import LeaveBalance

    mock_db = AsyncMock()
    user_id = 8
    local_lt = LeaveType(id=1, name="Annual Leave", code="AL", days_per_year=15, is_active=True)
    custom_bal = LeaveBalance(id=1, user_id=user_id, leave_type_id=1, year=2026, allocated_days=15.0, used_days=5.0)

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=None), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]), \
         patch.object(LeaveBalanceRepository, "get_by_user_and_year", new_callable=AsyncMock, return_value=[custom_bal]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        assert b.source == "local"
        assert b.is_live is False
        assert b.sync_error is None
        assert b.allocated_days == 15.0
        assert b.used_days == 5.0
        assert b.remaining_days == 10.0


@pytest.mark.asyncio
async def test_leave_balances_unconfigured_keka_returns_local():
    """When Keka integration is unconfigured, local balances are returned safely."""
    from app.modules.leave_balances.service import LeaveBalanceService

    mock_db = AsyncMock()
    user_id = 9
    local_lt = LeaveType(id=1, name="Sick Leave", code="SL", days_per_year=12, is_active=True)

    with patch.object(KekaAuthManager, "is_configured", return_value=False), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]), \
         patch.object(LeaveBalanceRepository, "get_by_user_and_year", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        assert b.source == "local"
        assert b.is_live is False
        assert b.allocated_days == 12.0
        assert b.remaining_days == 12.0


@pytest.mark.asyncio
async def test_leave_balances_keka_api_failure_indicates_error():
    """When Keka API call fails, fallback returns local balance with explicit sync_error and is_live=False."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 10
    mapping = KekaEmployeeMapping(id=2, local_user_id=user_id, keka_employee_id="keka-uuid-10")
    local_lt = LeaveType(id=1, name="Casual Leave", code="CL", days_per_year=10, is_active=True)

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, side_effect=KekaAPIError("Keka upstream server error (HTTP 500)", status_code=500)), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]), \
         patch.object(LeaveBalanceRepository, "get_by_user_and_year", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        assert b.source == "local"
        assert b.is_live is False
        assert b.sync_error is not None
        assert "500" in b.sync_error
        # Balances are NOT fabricated as Keka balances
        assert b.allocated_days == 10.0


@pytest.mark.asyncio
async def test_leave_balances_custom_keka_leave_types():
    """Custom Keka leave types not in local database are preserved and returned with their Keka IDs."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 11
    mapping = KekaEmployeeMapping(id=3, local_user_id=user_id, keka_employee_id="keka-uuid-11")

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "keka-uuid-11",
                "leaveBalance": [
                    {
                        "leaveTypeId": "keka-custom-paternity-guid",
                        "leaveTypeName": "Paternity Leave",
                        "availableBalance": 5.0,
                        "used": 0.0,
                        "annualQuota": 5.0,
                        "accrued": 5.0,
                    }
                ],
            }
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        assert b.leave_type_name == "Paternity Leave"
        assert b.keka_leave_type_id == "keka-custom-paternity-guid"
        assert b.available_balance == 5.0
        assert b.annual_quota == 5.0
        assert b.source == "keka"
        assert b.is_live is True


@pytest.mark.asyncio
async def test_leave_balances_pagination_handling():
    """Verify KekaClient.get_leave_balances supports pagination parameters cleanly."""
    with patch.object(KekaClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"succeeded": True, "data": []}
        res = await KekaClient.get_leave_balances(
            employee_ids=["emp-uuid-1"],
            page_number=2,
            page_size=50,
        )
        mock_get.assert_called_once_with(
            "/time/leavebalance",
            params={
                "pageNumber": 2,
                "pageSize": 50,
                "employeeIds": "emp-uuid-1",
            },
        )
        assert res == {"succeeded": True, "data": []}


@pytest.mark.asyncio
async def test_leave_balances_response_field_mapping_exact():
    """Verify exact mapping of verified Keka response fields without inventing fields."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 12
    mapping = KekaEmployeeMapping(id=4, local_user_id=user_id, keka_employee_id="keka-uuid-12")

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "keka-uuid-12",
                "leaveBalance": [
                    {
                        "leaveTypeId": "lt-uuid-exact",
                        "leaveTypeName": "Privilege Leave",
                        "availableBalance": 12.25,
                        "used": 4.75,
                        "annualQuota": 17.0,
                        "accrued": 14.5,
                    }
                ],
            }
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        # Exact field mapping verification
        assert b.keka_leave_type_id == "lt-uuid-exact"
        assert b.leave_type_name == "Privilege Leave"
        assert b.available_balance == 12.25
        assert b.remaining_days == 12.25
        assert b.used_days == 4.75
        assert b.annual_quota == 17.0
        assert b.allocated_days == 17.0
        assert b.accrued_days == 14.5
        assert b.source == "keka"
        assert b.is_live is True
        assert b.sync_error is None


@pytest.mark.asyncio
async def test_leave_balances_employee_isolation_second_entry():
    """Verify that when Keka returns multiple employees, the requested employee's balances are isolated (second entry)."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 15
    target_keka_id = "target-emp-uuid"
    mapping = KekaEmployeeMapping(id=5, local_user_id=user_id, keka_employee_id=target_keka_id)

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "other-emp-uuid",
                "leaveBalance": [
                    {
                        "leaveTypeId": "other-lt-uuid",
                        "leaveTypeName": "Other Employee Leave",
                        "availableBalance": 99.0,
                    }
                ],
            },
            {
                "employeeId": "target-emp-uuid",
                "leaveBalance": [
                    {
                        "leaveTypeId": "target-lt-uuid",
                        "leaveTypeName": "Target Employee Leave",
                        "availableBalance": 7.5,
                        "used": 2.5,
                        "annualQuota": 10.0,
                    }
                ],
            },
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        # Must strictly be target employee's balances, never other employee's
        assert b.leave_type_name == "Target Employee Leave"
        assert b.available_balance == 7.5
        assert b.keka_leave_type_id == "target-lt-uuid"
        assert b.source == "keka"
        assert b.is_live is True


@pytest.mark.asyncio
async def test_leave_balances_employee_isolation_no_matching_employee():
    """Verify that if Keka returns entries but none match the employee ID, other employees' balances are never returned."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 16
    target_keka_id = "target-emp-uuid"
    mapping = KekaEmployeeMapping(id=6, local_user_id=user_id, keka_employee_id=target_keka_id)
    local_lt = LeaveType(id=1, name="Casual Leave", code="CL", days_per_year=10, is_active=True)

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "completely-different-emp-uuid",
                "leaveBalance": [
                    {
                        "leaveTypeId": "other-lt-uuid",
                        "leaveTypeName": "Other Employee Leave",
                        "availableBalance": 99.0,
                    }
                ],
            }
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]), \
         patch.object(LeaveBalanceRepository, "get_by_user_and_year", new_callable=AsyncMock, return_value=[]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        # Never returns other employee's balances
        assert b.leave_type_name == "Casual Leave"
        assert b.source == "local"
        assert b.is_live is False
        assert b.sync_error is not None
        assert "not found in Keka leave balance response" in b.sync_error


@pytest.mark.asyncio
async def test_leave_balances_name_collision_with_already_mapped_local_leave_type():
    """Verify that a custom Keka leave type sharing a name with a local leave type already mapped to another Keka ID does NOT collide."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 17
    mapping = KekaEmployeeMapping(id=7, local_user_id=user_id, keka_employee_id="keka-emp-17")

    # Local leave type already mapped to 'keka-primary-sick'
    local_lt = LeaveType(
        id=1,
        name="Sick Leave",
        code="SL",
        keka_leave_type_id="keka-primary-sick",
        is_active=True,
    )

    # Keka returns a custom/special sick leave with different Keka ID 'keka-special-sick'
    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "keka-emp-17",
                "leaveBalance": [
                    {
                        "leaveTypeId": "keka-special-sick",
                        "leaveTypeName": "Sick Leave",
                        "availableBalance": 5.0,
                        "used": 0.0,
                        "annualQuota": 5.0,
                    }
                ],
            }
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        # Does NOT collide with local_lt.id (1), but receives distinct synthetic ID (1000)
        assert b.id != 1
        assert b.keka_leave_type_id == "keka-special-sick"
        assert b.leave_type_name == "Sick Leave"
        assert b.available_balance == 5.0
        assert b.source == "keka"
        assert b.is_live is True


@pytest.mark.asyncio
async def test_leave_balances_name_fallback_for_unmapped_local_leave_type():
    """Verify that name fallback successfully maps to an unmapped local leave type."""
    from app.modules.leave_balances.service import LeaveBalanceService
    from app.modules.keka.model import KekaEmployeeMapping

    mock_db = AsyncMock()
    user_id = 18
    mapping = KekaEmployeeMapping(id=8, local_user_id=user_id, keka_employee_id="keka-emp-18")

    # Local leave type has NO keka_leave_type_id (unmapped)
    local_lt = LeaveType(
        id=2,
        name="Maternity Leave",
        code="ML",
        keka_leave_type_id=None,
        is_active=True,
    )

    keka_api_response = {
        "succeeded": True,
        "data": [
            {
                "employeeId": "keka-emp-18",
                "leaveBalance": [
                    {
                        "leaveTypeId": "keka-maternity-guid",
                        "leaveTypeName": "Maternity Leave",
                        "availableBalance": 84.0,
                        "used": 0.0,
                        "annualQuota": 84.0,
                    }
                ],
            }
        ],
    }

    with patch.object(KekaAuthManager, "is_configured", return_value=True), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=keka_api_response), \
         patch.object(LeaveTypeRepository, "get_all", new_callable=AsyncMock, return_value=[local_lt]):

        balances = await LeaveBalanceService.get_user_balances(mock_db, user_id=user_id, year=2026)

        assert len(balances) == 1
        b = balances[0]
        # Maps to unmapped local_lt.id (2)
        assert b.id == 2
        assert b.leave_type_id == 2
        assert b.leave_type_name == "Maternity Leave"
        assert b.keka_leave_type_id == "keka-maternity-guid"
        assert b.available_balance == 84.0
        assert b.source == "keka"
        assert b.is_live is True


@pytest.mark.asyncio
async def test_keka_leave_payload_field_mapping_and_identifiers():
    leave = make_test_leave_request(
        id=101,
        user_id=1,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 3),
        reason="Family event",
        leave_duration_type="full_day",
        keka_leave_type_id="keka-annual-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-uuid-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": "a0000000-0000-0000-0000-000000000999"}) as mock_create:

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        assert result["synced"] is True
        assert result["keka_leave_request_id"] == "a0000000-0000-0000-0000-000000000999"
        mock_create.assert_called_once_with(
            employee_id="keka-emp-uuid-42",
            from_date="2026-11-02T00:00:00Z",
            to_date="2026-11-03T00:00:00Z",
            leave_type_id="keka-annual-guid",
            reason="Family event",
            requested_by="keka-emp-uuid-42",
            from_session=0,
            to_session=1,
            note="Local Leave ID: 101",
        )


@pytest.mark.asyncio
async def test_keka_leave_session_mapping_first_half():
    leave = make_test_leave_request(
        id=102,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Dentist appointment",
        leave_duration_type="half_day",
        half_day_period="first",
        keka_leave_type_id="keka-casual-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-uuid-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": "b1111111-1111-1111-1111-111111111111"}) as mock_create:

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        mock_create.assert_called_once_with(
            employee_id="keka-emp-uuid-42",
            from_date="2026-11-05T00:00:00Z",
            to_date="2026-11-05T00:00:00Z",
            leave_type_id="keka-casual-guid",
            reason="Dentist appointment",
            requested_by="keka-emp-uuid-42",
            from_session=0,
            to_session=0,
            note="Local Leave ID: 102",
        )


@pytest.mark.asyncio
async def test_keka_leave_session_mapping_second_half():
    leave = make_test_leave_request(
        id=103,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Personal work",
        leave_duration_type="half_day",
        half_day_period="second",
        keka_leave_type_id="keka-casual-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-uuid-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": "b2222222-2222-2222-2222-222222222222"}) as mock_create:

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        mock_create.assert_called_once_with(
            employee_id="keka-emp-uuid-42",
            from_date="2026-11-05T00:00:00Z",
            to_date="2026-11-05T00:00:00Z",
            leave_type_id="keka-casual-guid",
            reason="Personal work",
            requested_by="keka-emp-uuid-42",
            from_session=1,
            to_session=1,
            note="Local Leave ID: 103",
        )


@pytest.mark.asyncio
async def test_keka_leave_half_day_spanning_multiple_dates_rejected():
    leave = make_test_leave_request(
        id=104,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 6),
        reason="Invalid half day",
        leave_duration_type="half_day",
        half_day_period="first",
        keka_leave_type_id="keka-casual-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock) as mock_create:
        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert "cannot span multiple dates" in leave.last_sync_error.lower()
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_unsupported_hourly_partial_day_marked_local_only():
    leave = make_test_leave_request(
        id=105,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Partial doctor checkup",
        leave_duration_type="partial_day",
        keka_leave_type_id="keka-casual-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock) as mock_create:
        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert leave.synced_to_keka is False
        assert "partial-day / hourly leaves are managed locally" in leave.last_sync_error.lower()
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_idempotency_prevents_duplicate_submission():
    leave = make_test_leave_request(
        id=106,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Already synced",
        keka_leave_type_id="keka-casual-guid",
    )
    leave.synced_to_keka = True
    leave.keka_leave_request_id = "keka-guid-existing-106"
    leave.last_synced_at = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
    mock_db = AsyncMock()

    with patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock) as mock_create:
        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        assert result["synced"] is True
        assert result["keka_leave_request_id"] == "keka-guid-existing-106"
        assert "already synchronized" in result["message"].lower()
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_missing_leave_type_mapping_fails_cleanly():
    leave = make_test_leave_request(
        id=107,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Unmapped leave type",
        keka_leave_type_id=None,
    )
    leave.leave_type.keka_leave_type_id = None
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
         patch.object(LeaveTypeRepository, "get_by_id", new_callable=AsyncMock, return_value=None), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock) as mock_create:

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert "no keka leave type id mapped" in leave.last_sync_error.lower()
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_empty_or_invalid_response_data_does_not_persist_fake_id():
    leave = make_test_leave_request(
        id=108,
        user_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        reason="Empty data response",
        keka_leave_type_id="keka-guid-1",
    )
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": None}):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert leave.synced_to_keka is False
        assert leave.keka_leave_request_id is None
        assert "did not contain a valid leave request id" in leave.last_sync_error.lower()


@pytest.mark.asyncio
async def test_keka_leave_status_sync_employee_isolation():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave_own = make_test_leave_request(id=201, user_id=1)
    local_leave_own.keka_leave_request_id = "req-own-201"
    local_leave_own.status = "Pending"

    mock_db = AsyncMock()

    keka_records = [
        {
            "id": "req-other-999",
            "employeeId": "keka-other-emp",
            "status": "Approved",
        },
        {
            "id": "req-own-201",
            "employeeId": "keka-own-emp",
            "status": "Approved",
        },
    ]

    async def mock_get_by_keka_id(db, keka_id):
        if keka_id == "req-own-201":
            return local_leave_own
        return None

    async def mock_get_mapping(db, user_id):
        if user_id == 1:
            return KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-own-emp")
        return None

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", side_effect=mock_get_by_keka_id), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", side_effect=mock_get_mapping):

        result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert result["total_keka_records"] == 2
        assert result["matched_local_records"] == 1
        assert result["updated_count"] == 1
        assert local_leave_own.status == "Approved"


@pytest.mark.asyncio
async def test_keka_leave_status_sync_unknown_status_mapped_safely():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave = make_test_leave_request(id=202, user_id=1)
    local_leave.keka_leave_request_id = "req-unknown-202"
    local_leave.status = "Pending"

    mock_db = AsyncMock()
    keka_records = [
        {
            "id": "req-unknown-202",
            "employeeId": "keka-emp-1",
            "status": "UnknownCustomState",
        }
    ]

    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=local_leave), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

        result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert result["matched_local_records"] == 1
        assert result["updated_count"] == 0
        assert local_leave.status == "Pending"


@pytest.mark.asyncio
async def test_keka_leave_approval_does_not_deduct_local_balance_for_keka_mapped_employee():
    from app.modules.leave_requests.service import LeaveRequestService
    from app.modules.keka.model import KekaEmployeeMapping
    from app.modules.leave_requests.validator import LeaveRequestValidator

    leave = make_test_leave_request(id=301, user_id=1, status="Pending")
    mock_db = AsyncMock()
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-mapped-user")

    with patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=leave), \
         patch.object(LeaveRequestValidator, "calculate_working_days", new_callable=AsyncMock, return_value=2.0), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(LeaveBalanceRepository, "get_specific_balance", new_callable=AsyncMock) as mock_get_bal, \
         patch.object(LeaveRequestRepository, "update_status", new_callable=AsyncMock, return_value=leave):

        approved = await LeaveRequestService.approve_leave_request(mock_db, request_id=301, admin_user=ADMIN_USER)

        assert approved is not None
        mock_get_bal.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_cancellation_does_not_refund_local_balance_for_keka_mapped_employee():
    from app.modules.leave_requests.service import LeaveRequestService
    from app.modules.keka.model import KekaEmployeeMapping
    from app.modules.leave_requests.validator import LeaveRequestValidator

    leave = make_test_leave_request(id=302, user_id=1, status="Approved")
    mock_db = AsyncMock()
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-mapped-user")

    with patch.object(LeaveRequestRepository, "get_by_id", new_callable=AsyncMock, return_value=leave), \
         patch.object(LeaveRequestValidator, "calculate_working_days", new_callable=AsyncMock, return_value=2.0), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(LeaveBalanceRepository, "get_specific_balance", new_callable=AsyncMock) as mock_get_bal, \
         patch.object(LeaveRequestRepository, "update_status", new_callable=AsyncMock, return_value=leave):

        cancelled = await LeaveRequestService.cancel_leave_request(mock_db, request_id=302, current_user=ADMIN_USER)

        assert cancelled is not None
        mock_get_bal.assert_not_called()


@pytest.mark.asyncio
async def test_keka_leave_status_sync_preserves_local_cancellation_when_keka_reports_pending():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave = make_test_leave_request(id=401, user_id=1, status="Cancelled")
    local_leave.keka_leave_request_id = "keka-req-401"
    mock_db = AsyncMock()
    keka_records = [{"id": "keka-req-401", "employeeId": "keka-emp-1", "status": 0}]
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=local_leave), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

        result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert local_leave.status == "Cancelled"
        assert result["updated_count"] == 0
        assert "cancelled locally, but remains Pending in Keka" in (local_leave.last_sync_error or "")


@pytest.mark.asyncio
async def test_keka_leave_status_sync_preserves_local_cancellation_when_keka_reports_approved():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave = make_test_leave_request(id=402, user_id=1, status="Cancelled")
    local_leave.keka_leave_request_id = "keka-req-402"
    mock_db = AsyncMock()
    keka_records = [{"id": "keka-req-402", "employeeId": "keka-emp-1", "status": 1}]
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=local_leave), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

        result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert local_leave.status == "Cancelled"
        assert result["updated_count"] == 0
        assert "cancelled locally, but remains Approved in Keka" in (local_leave.last_sync_error or "")


@pytest.mark.asyncio
async def test_keka_leave_status_sync_handles_cancellation_when_keka_reports_cancelled():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave = make_test_leave_request(id=403, user_id=1, status="Cancelled")
    local_leave.keka_leave_request_id = "keka-req-403"
    mock_db = AsyncMock()
    keka_records = [{"id": "keka-req-403", "employeeId": "keka-emp-1", "status": 3}]
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=local_leave), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

        result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert local_leave.status == "Cancelled"
        assert result["updated_count"] == 0
        assert local_leave.last_sync_error is None


@pytest.mark.asyncio
async def test_keka_leave_status_sync_repeated_sync_preserves_local_cancellation():
    from app.modules.keka.model import KekaEmployeeMapping
    local_leave = make_test_leave_request(id=404, user_id=1, status="Cancelled")
    local_leave.keka_leave_request_id = "keka-req-404"
    mock_db = AsyncMock()
    keka_records = [{"id": "keka-req-404", "employeeId": "keka-emp-1", "status": "Approved"}]
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
         patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=local_leave), \
         patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

        first_sync = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)
        assert local_leave.status == "Cancelled"
        assert first_sync["updated_count"] == 0

        second_sync = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)
        assert local_leave.status == "Cancelled"
        assert second_sync["updated_count"] == 0
        assert "cancelled locally, but remains Approved in Keka" in (local_leave.last_sync_error or "")


@pytest.mark.asyncio
async def test_keka_leave_concurrent_duplicate_submissions_dispatches_only_once():
    leave = make_test_leave_request(
        id=501,
        user_id=1,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 10),
        reason="Concurrent test",
        keka_leave_type_id="keka-type-guid",
    )
    mock_db = AsyncMock()
    real_keka_guid = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    dispatch_count = 0

    async def mock_create_leave_request(*args, **kwargs):
        nonlocal dispatch_count
        dispatch_count += 1
        await asyncio.sleep(0.05)
        return {"succeeded": True, "data": real_keka_guid}

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
         patch.object(KekaClient, "create_leave_request", side_effect=mock_create_leave_request):

        res1, res2 = await asyncio.gather(
            KekaLeaveService.sync_leave_to_keka(mock_db, leave),
            KekaLeaveService.sync_leave_to_keka(mock_db, leave),
        )

        assert dispatch_count == 1
        assert res1["success"] is True
        assert res2["success"] is True
        assert res1["keka_leave_request_id"] == real_keka_guid
        assert res2["keka_leave_request_id"] == real_keka_guid
        assert leave.synced_to_keka is True
        assert leave.keka_leave_request_id == real_keka_guid


@pytest.mark.asyncio
async def test_keka_leave_guid_validation_accepts_valid_uuid():
    leave = make_test_leave_request(
        id=601,
        user_id=1,
        start_date=date(2026, 11, 12),
        end_date=date(2026, 11, 12),
        reason="Valid GUID",
        keka_leave_type_id="keka-type-guid",
    )
    mock_db = AsyncMock()
    valid_guid = "e7492c13-a442-4f36-a19f-b7650f9dd3c4"

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": valid_guid}):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is True
        assert result["synced"] is True
        assert result["keka_leave_request_id"] == valid_guid
        assert leave.synced_to_keka is True
        assert leave.keka_leave_request_id == valid_guid
        assert leave.last_sync_error is None


@pytest.mark.asyncio
async def test_keka_leave_guid_validation_rejects_empty_value():
    leave = make_test_leave_request(
        id=602,
        user_id=1,
        start_date=date(2026, 11, 12),
        end_date=date(2026, 11, 12),
        reason="Empty GUID",
        keka_leave_type_id="keka-type-guid",
    )
    mock_db = AsyncMock()

    with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
         patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": ""}):

        result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

        assert result["success"] is False
        assert result["synced"] is False
        assert result["keka_leave_request_id"] is None
        assert leave.synced_to_keka is False
        assert leave.keka_leave_request_id is None
        assert "did not contain a valid leave request id" in (leave.last_sync_error or "").lower()


@pytest.mark.asyncio
async def test_keka_leave_guid_validation_rejects_malformed_values():
    mock_db = AsyncMock()
    malformed_values = ["null", "error", "OK", "123", "not-a-uuid-string"]

    for idx, bad_val in enumerate(malformed_values, start=610):
        leave = make_test_leave_request(
            id=idx,
            user_id=1,
            start_date=date(2026, 11, 12),
            end_date=date(2026, 11, 12),
            reason=f"Testing {bad_val}",
            keka_leave_type_id="keka-type-guid",
        )

        with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
             patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": bad_val}):

            result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

            assert result["success"] is False
            assert result["synced"] is False
            assert result["keka_leave_request_id"] is None
            assert leave.synced_to_keka is False
            assert leave.keka_leave_request_id is None
            assert "did not contain a valid leave request id" in (leave.last_sync_error or "").lower()


@pytest.mark.asyncio
async def test_keka_leave_guid_validation_rejects_unexpected_envelope():
    mock_db = AsyncMock()
    valid_guid = "e7492c13-a442-4f36-a19f-b7650f9dd3c4"
    invalid_envelopes = [
        {"succeeded": False, "data": valid_guid},
        {"data": valid_guid},
        "not-a-dictionary",
        None,
    ]

    for idx, env in enumerate(invalid_envelopes, start=630):
        leave = make_test_leave_request(
            id=idx,
            user_id=1,
            start_date=date(2026, 11, 12),
            end_date=date(2026, 11, 12),
            reason="Envelope test",
            keka_leave_type_id="keka-type-guid",
        )

        with patch.object(KekaLeaveService, "get_keka_employee_id_for_user", new_callable=AsyncMock, return_value="keka-emp-42"), \
             patch.object(KekaClient, "create_leave_request", new_callable=AsyncMock, return_value=env):

            result = await KekaLeaveService.sync_leave_to_keka(mock_db, leave)

            assert result["success"] is False
            assert result["synced"] is False
            assert leave.synced_to_keka is False
            assert leave.keka_leave_request_id is None
            assert "did not contain a valid leave request id" in (leave.last_sync_error or "").lower()


@pytest.mark.asyncio
async def test_keka_leave_status_sync_maps_all_known_integer_and_string_statuses():
    from app.modules.keka.model import KekaEmployeeMapping
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")
    mock_db = AsyncMock()

    status_cases = [
        (0, "Pending"),
        (1, "Approved"),
        (2, "Rejected"),
        (3, "Cancelled"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("canceled", "Cancelled"),
    ]

    for idx, (raw_st, expected_local) in enumerate(status_cases, start=700):
        initial_status = "Rejected" if expected_local != "Rejected" else "Pending"
        leave = make_test_leave_request(id=idx, user_id=1, status=initial_status)
        req_id = f"keka-status-{idx}"
        leave.keka_leave_request_id = req_id

        keka_records = [{"id": req_id, "employeeId": "keka-emp-1", "status": raw_st}]

        with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
             patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=leave), \
             patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

            result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

            assert result["matched_local_records"] == 1
            assert result["updated_count"] == 1
            assert leave.status == expected_local


@pytest.mark.asyncio
async def test_keka_leave_status_sync_ignores_unknown_statuses_safely():
    from app.modules.keka.model import KekaEmployeeMapping
    mapping = KekaEmployeeMapping(id=1, local_user_id=1, keka_employee_id="keka-emp-1")
    mock_db = AsyncMock()

    unknown_cases = ["UnderReview", "OnHold", "UnknownStatus", 99, -1, None, {}]

    for idx, unk_st in enumerate(unknown_cases, start=800):
        leave = make_test_leave_request(id=idx, user_id=1, status="Pending")
        req_id = f"keka-unk-{idx}"
        leave.keka_leave_request_id = req_id

        keka_records = [{"id": req_id, "employeeId": "keka-emp-1", "status": unk_st}]

        with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_records), \
             patch.object(LeaveRequestRepository, "get_by_keka_id", new_callable=AsyncMock, return_value=leave), \
             patch.object(KekaEmployeeMappingRepository, "get_by_local_user_id", new_callable=AsyncMock, return_value=mapping):

            result = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

            assert result["matched_local_records"] == 1
            assert result["updated_count"] == 0
            assert leave.status == "Pending"





