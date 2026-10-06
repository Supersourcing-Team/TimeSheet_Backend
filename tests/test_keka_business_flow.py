from datetime import date, datetime
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.departments.model import Department
from app.modules.holidays.model import Holiday
from app.modules.keka.attendance_service import KekaAttendanceService
from app.modules.keka.leave_service import KekaLeaveService
from app.modules.keka.model import KekaEmployeeMapping
from app.modules.keka.service import KekaService
from app.modules.leave_requests.model import LeaveRequest
from app.modules.leave_types.model import LeaveType
from app.modules.roles.model import Role
from app.modules.users.model import User
from app.modules.working_calendar.model import WorkingCalendar
from app.services.keka.keka_client import KekaClient

client = TestClient(app)


def make_admin_user():
    u = User(
        id=1,
        email="admin@test.com",
        employee_id="ADMIN001",
        first_name="Admin",
        last_name="User",
        role_id=1,
        status="Active",
    )
    u.role = Role(id=1, name="Admin")
    return u


ADMIN_USER = make_admin_user()


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. EMPLOYEE SYNC BUSINESS FLOW (Keka -> Local User & Department)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_employees_from_keka_updates_existing_and_status():
    mock_db = AsyncMock()

    # Existing local user
    existing_user = User(
        id=10,
        email="john.doe@acme.com",
        employee_id="EMP10",
        first_name="John",
        last_name="OldName",
        status="Active",
        department_id=None,
    )
    dept = Department(id=5, name="Engineering")

    # Mocks for database queries
    class MockUsersResult:
        def scalars(self):
            class S:
                def all(self):
                    return [existing_user]
            return S()

    class MockDeptResult:
        def scalars(self):
            class S:
                def all(self):
                    return [dept]
            return S()

    class MockRoleResult:
        def scalar_one_or_none(self):
            return Role(id=2, name="Employee")

    class MockMappingsResult:
        def scalars(self):
            class S:
                def all(self):
                    return []
            return S()

    # Database query execution returns
    mock_db.execute.side_effect = [
        MockUsersResult(),     # select(User)
        MockDeptResult(),      # select(Department)
        MockRoleResult(),      # select(Role) default
        MockMappingsResult(),  # select(KekaEmployeeMapping)
    ]

    # Keka returns John Doe with updated name, resigned/relieved status, and Engineering department
    keka_employees_payload = {
        "data": [
            {
                "id": "keka-guid-10",
                "employeeNumber": "EMP10",
                "email": "john.doe@acme.com",
                "firstName": "John",
                "lastName": "NewName",
                "employmentStatus": "Relieved",
                "department": "Engineering",
                "dateOfJoining": "2024-01-15T00:00:00",
            }
        ]
    }

    with patch.object(KekaClient, "get_all_employees", new_callable=AsyncMock, return_value=keka_employees_payload):
        summary = await KekaService.sync_employees_from_keka(
            mock_db, update_existing=True, create_missing=False
        )

        assert summary["total_keka_employees"] == 1
        assert summary["updated_count"] == 1
        assert summary["mapped_count"] == 1
        assert summary["conflicts_count"] == 0

        # Assert local user was updated to Inactive due to Relieved status
        assert existing_user.status == "Inactive"
        assert existing_user.last_name == "NewName"
        assert existing_user.department_id == 5
        assert existing_user.joining_date == date(2024, 1, 15)

        # Assert db.commit was called
        mock_db.commit.assert_awaited()


# =============================================================================
# 2. DEPARTMENT SYNC BUSINESS FLOW (Keka -> Local Department)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_departments_from_keka():
    mock_db = AsyncMock()

    existing_dept = Department(id=1, name="HR")

    class MockDeptResult:
        def scalars(self):
            class S:
                def all(self):
                    return [existing_dept]
            return S()

    mock_db.execute.return_value = MockDeptResult()

    keka_depts = [
        {"id": "dept-1", "name": "HR"},            # Existing -> skip
        {"id": "dept-2", "name": "Product Design"}, # New -> insert
    ]

    with patch.object(KekaClient, "get_departments", new_callable=AsyncMock, return_value={"data": keka_depts}):
        summary = await KekaService.sync_departments_from_keka(mock_db)

        assert summary["total_keka_departments"] == 2
        assert summary["created_count"] == 1
        assert summary["existing_count"] == 1
        mock_db.commit.assert_awaited()


# =============================================================================
# 3. HOLIDAY SYNC BUSINESS FLOW (Keka -> Local Holiday)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_holidays_from_keka():
    mock_db = AsyncMock()

    keka_calendars = [{"id": "cal-guid-1", "name": "India Holidays 2026"}]
    keka_holidays = [
        {"id": "h-1", "name": "Republic Day", "startDate": "2026-01-26T00:00:00"},
        {"id": "h-2", "name": "Independence Day", "startDate": "2026-08-15T00:00:00"},
    ]

    with patch.object(KekaClient, "get_holiday_calendars", new_callable=AsyncMock, return_value={"data": keka_calendars}), \
         patch.object(KekaClient, "get_calendar_holidays", new_callable=AsyncMock, return_value={"data": keka_holidays}), \
         patch("app.modules.holidays.repository.HolidayRepository.get_by_date", new_callable=AsyncMock, side_effect=[None, Holiday(id=99, name="Independence Day")]):

        summary = await KekaService.sync_holidays_from_keka(mock_db, calendar_id="cal-guid-1")

        assert summary["total_keka_holidays"] == 2
        assert summary["created_count"] == 1
        assert summary["skipped_existing_count"] == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited()


# =============================================================================
# 4. LEAVE TYPE SYNC BUSINESS FLOW (Keka -> Local LeaveType)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_leave_types_from_keka():
    mock_db = AsyncMock()

    local_lt = LeaveType(id=1, name="Casual Leave", keka_leave_type_id=None)

    class MockLTResult:
        def scalars(self):
            class S:
                def all(self):
                    return [local_lt]
            return S()

    mock_db.execute.return_value = MockLTResult()

    keka_types = [
        {"id": "keka-lt-uuid-casual", "name": "Casual Leave"},
        {"id": "keka-lt-uuid-sick", "name": "Sick Leave"},
    ]

    with patch.object(KekaClient, "get_leave_types", new_callable=AsyncMock, return_value={"data": keka_types}):
        summary = await KekaService.sync_leave_types_from_keka(mock_db)

        assert summary["total_keka_leave_types"] == 2
        assert summary["matched_count"] == 1
        assert local_lt.keka_leave_type_id == "keka-lt-uuid-casual"
        mock_db.commit.assert_awaited()


# =============================================================================
# 5. BULK UNSYNCED LEAVES PUSH FLOW (Local -> Keka)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_all_unsynced_leaves():
    mock_db = AsyncMock()

    req1 = LeaveRequest(
        id=101,
        user_id=1,
        leave_type_id=1,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 2),
        leave_duration_type="full_day",
        status="Approved",
        synced_to_keka=False,
    )
    req2 = LeaveRequest(
        id=102,
        user_id=2,
        leave_type_id=1,
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        leave_duration_type="full_day",
        status="Approved",
        synced_to_keka=False,
    )

    with patch("app.modules.leave_requests.repository.LeaveRequestRepository.get_unsynced_leaves", new_callable=AsyncMock, return_value=[req1, req2]), \
         patch.object(KekaLeaveService, "sync_leave_to_keka", new_callable=AsyncMock, side_effect=[
             {"success": True, "synced": True, "keka_leave_request_id": "keka-req-1"},
             {"success": False, "synced": False, "error": "No mapping"},
         ]):

        res = await KekaLeaveService.sync_all_unsynced_leaves(mock_db)

        assert res["total_found"] == 2
        assert res["synced_count"] == 1
        assert res["failed_count"] == 1


# =============================================================================
# 6. LEAVE STATUS SYNC FLOW (Keka -> Local)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_leave_statuses_from_keka():
    mock_db = AsyncMock()

    local_req = LeaveRequest(
        id=200,
        keka_leave_request_id="keka-req-guid-200",
        status="Pending",
    )

    keka_leaves = [
        {
            "id": "keka-req-guid-200",
            "status": "Approved",
        }
    ]

    with patch.object(KekaClient, "get_all_pages", new_callable=AsyncMock, return_value=keka_leaves), \
         patch("app.modules.leave_requests.repository.LeaveRequestRepository.get_by_keka_id", new_callable=AsyncMock, return_value=local_req):

        res = await KekaLeaveService.sync_leave_statuses_from_keka(mock_db)

        assert res["total_keka_records"] == 1
        assert res["matched_local_records"] == 1
        assert res["updated_count"] == 1
        assert local_req.status == "Approved"
        mock_db.commit.assert_awaited()


# =============================================================================
# 7. ATTENDANCE TIME ENTRY PUSH FLOW (Local -> Keka)
# =============================================================================


@pytest.mark.asyncio
async def test_push_time_entry_for_user():
    mock_db = AsyncMock()

    mapping = KekaEmployeeMapping(
        local_user_id=42,
        keka_employee_id="keka-emp-guid-42",
        keka_employee_number="EMP42",
    )

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "log_attendance_time_entry", new_callable=AsyncMock, return_value={"succeeded": True}):

        res = await KekaAttendanceService.push_time_entry_for_user(
            db=mock_db,
            user_id=42,
            timestamp=datetime(2026, 10, 6, 9, 30, 0),
            punch_status=1,
            note="Morning Punch",
        )

        assert res["success"] is True
        assert res["local_user_id"] == 42
        assert res["keka_employee_id"] == "keka-emp-guid-42"
        assert res["punch_status"] == 1


# =============================================================================
# 8. WEEKLY OFF POLICY SYNC FLOW (Keka -> Working Calendar)
# =============================================================================


@pytest.mark.asyncio
async def test_sync_weekly_off_policy_to_calendar():
    mock_db = AsyncMock()

    calendar = WorkingCalendar(
        id=1,
        full_day_hours=8.0,
        working_days={
            "monday": True, "tuesday": True, "wednesday": True,
            "thursday": True, "friday": True, "saturday": True, "sunday": False
        },
    )

    updated_cal = WorkingCalendar(
        id=1,
        full_day_hours=8.0,
        working_days={
            "monday": True, "tuesday": True, "wednesday": True,
            "thursday": True, "friday": True, "saturday": False, "sunday": False
        },
    )

    keka_policy = {
        "id": "policy-1",
        "name": "Standard Weekend Off",
        "weeklyOffDays": ["Saturday", "Sunday"],
    }

    with patch.object(KekaClient, "get_weekly_off_policies", new_callable=AsyncMock, return_value={"data": [keka_policy]}), \
         patch("app.modules.working_calendar.service.WorkingCalendarService.get_config", new_callable=AsyncMock, return_value=calendar), \
         patch("app.modules.working_calendar.service.WorkingCalendarService.update_config", new_callable=AsyncMock, return_value=updated_cal):

        res = await KekaAttendanceService.sync_weekly_off_policy_to_calendar(mock_db)

        assert res["success"] is True
        assert res["policy_id"] == "policy-1"
        assert res["new_working_days"]["saturday"] is False
        assert res["new_working_days"]["sunday"] is False
        assert res["new_working_days"]["monday"] is True


# =============================================================================
# 9. ROUTE INTEGRATION TESTS FOR NEW SYNC ENDPOINTS
# =============================================================================


def test_sync_routes_accessible_by_admin():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaService, "sync_employees_from_keka", new_callable=AsyncMock, return_value={"total": 0}), \
         patch.object(KekaService, "sync_departments_from_keka", new_callable=AsyncMock, return_value={"created": 0}), \
         patch.object(KekaService, "sync_leave_types_from_keka", new_callable=AsyncMock, return_value={"updated": 0}), \
         patch.object(KekaService, "sync_holidays_from_keka", new_callable=AsyncMock, return_value={"created": 0}), \
         patch.object(KekaLeaveService, "sync_all_unsynced_leaves", new_callable=AsyncMock, return_value={"synced": 0}), \
         patch.object(KekaLeaveService, "sync_leave_statuses_from_keka", new_callable=AsyncMock, return_value={"updated": 0}), \
         patch.object(KekaAttendanceService, "sync_weekly_off_policy_to_calendar", new_callable=AsyncMock, return_value={"success": True}), \
         patch.object(KekaAttendanceService, "push_time_entry_for_user", new_callable=AsyncMock, return_value={"success": True}):

        assert client.post("/api/v1/keka/sync/employees", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/departments", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/leave-types", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/holidays", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/leaves/pending", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/leaves/statuses", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/sync/weekly-off", headers=admin_headers()).status_code == 200
        assert client.post("/api/v1/keka/attendance/push-time-entry?user_id=1&timestamp=2026-10-06T09:00:00", headers=admin_headers()).status_code == 200
