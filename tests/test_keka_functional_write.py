import app.core.models  # noqa: F401 - Ensure all SQLAlchemy mappers are initialized
from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytest

from app.modules.departments.model import Department
from app.modules.keka.attendance_service import KekaAttendanceService
from app.modules.keka.model import KekaEmployeeMapping
from app.modules.keka.schema import (
    KekaEmployeeCreateRequest,
    KekaEmployeeExitRequest,
    KekaJobDetailsUpdateRequest,
    KekaODCreateRequest,
    KekaWFHCreateRequest,
)
from app.modules.keka.service import KekaService
from app.modules.roles.model import Role
from app.modules.users.model import User
from app.services.keka.keka_client import KekaAPIError, KekaClient



# =============================================================================
# 1. CREATE EMPLOYEE END-TO-END FUNCTIONAL FLOW
# =============================================================================


@pytest.mark.asyncio
async def test_create_employee_flow_complete_success():
    mock_db = AsyncMock()

    # User and Mapping queries return None (new employee)
    class MockNoneResult:
        def scalar_one_or_none(self):
            return None

    dept = Department(id=3, name="Product Engineering")

    class MockDeptResult:
        def scalar_one_or_none(self):
            return dept

    role = Role(id=2, name="Employee")

    class MockRoleResult:
        def scalar_one_or_none(self):
            return role

    mock_db.execute.side_effect = [
        MockNoneResult(),   # Check user by email
        MockNoneResult(),   # Check user by emp_number
        MockDeptResult(),   # Resolve department
        MockRoleResult(),   # Default role
        MockNoneResult(),   # Check existing mapping
    ]

    req_payload = KekaEmployeeCreateRequest(
        employeeNumber="KEKA-9001",
        displayName="Marcus Vance",
        firstName="Marcus",
        middleName="Lee",
        lastName="Vance",
        email="marcus.vance@acme.com",
        mobileNumber="+14155552671",
        gender=1,  # Male
        dateOfBirth="1992-04-12T00:00:00Z",
        dateJoined="2026-03-01T00:00:00Z",
        department="Product Engineering",
        businessUnit="Software Division",
        jobTitle="Staff Engineer",
        secondaryJobTitle="Architect",
        location="San Francisco",
        legalEntity="Acme Global Inc",
        nationality="American",
    )

    keka_api_response = {
        "succeeded": True,
        "message": "Employee created successfully.",
        "errors": [],
        "data": "keka-guid-marcus-9001",
    }

    with patch.object(KekaClient, "create_employee", new_callable=AsyncMock, return_value=keka_api_response) as mock_keka_call:
        result = await KekaService.create_employee_flow(
            db=mock_db,
            payload=req_payload,
            create_local_user=True,
        )

        # 1. Verify Keka was called with all official fields
        mock_keka_call.assert_awaited_once()
        sent_body = mock_keka_call.await_args[0][0]
        assert sent_body["employeeNumber"] == "KEKA-9001"
        assert sent_body["firstName"] == "Marcus"
        assert sent_body["middleName"] == "Lee"
        assert sent_body["lastName"] == "Vance"
        assert sent_body["displayName"] == "Marcus Vance"
        assert sent_body["email"] == "marcus.vance@acme.com"
        assert sent_body["mobileNumber"] == "+14155552671"
        assert sent_body["gender"] == 1
        assert sent_body["dateOfBirth"] == "1992-04-12T00:00:00Z"
        assert sent_body["dateJoined"] == "2026-03-01T00:00:00Z"
        assert sent_body["department"] == "Product Engineering"
        assert sent_body["businessUnit"] == "Software Division"
        assert sent_body["jobTitle"] == "Staff Engineer"
        assert sent_body["secondaryJobTitle"] == "Architect"
        assert sent_body["location"] == "San Francisco"
        assert sent_body["legalEntity"] == "Acme Global Inc"
        assert sent_body["nationality"] == "American"

        # 2. Verify local DB operations
        assert mock_db.add.call_count == 2  # Added User and Mapping
        assert mock_db.commit.await_count >= 1

        # 3. Verify returned contract
        assert result["success"] is True
        assert result["keka_employee_id"] == "keka-guid-marcus-9001"
        assert result["email"] == "marcus.vance@acme.com"
        assert result["employee_number"] == "KEKA-9001"


@pytest.mark.asyncio
async def test_create_employee_flow_keka_error_prevents_db_corruption():
    mock_db = AsyncMock()

    req_payload = KekaEmployeeCreateRequest(
        firstName="Error",
        lastName="Case",
        email="error.case@acme.com",
    )

    with patch.object(KekaClient, "create_employee", new_callable=AsyncMock, side_effect=KekaAPIError("HTTP 400 Bad Request")):
        with pytest.raises(KekaAPIError):
            await KekaService.create_employee_flow(
                db=mock_db,
                payload=req_payload,
                create_local_user=True,
            )

        # Database must not have committed any records
        mock_db.commit.assert_not_awaited()


# =============================================================================
# 2. UPDATE JOB DETAILS END-TO-END FUNCTIONAL FLOW
# =============================================================================


@pytest.mark.asyncio
async def test_update_employee_job_details_flow_success():
    mock_db = AsyncMock()

    local_user = User(id=50, first_name="Dev", last_name="User", employee_id="EMP50", department_id=1)
    mapping = KekaEmployeeMapping(local_user_id=50, keka_employee_id="keka-guid-50", keka_employee_number="EMP50")

    class MockUserResult:
        def scalar_one_or_none(self):
            return local_user

    class MockDeptResult:
        def scalar_one_or_none(self):
            return Department(id=9, name="DevOps")

    mock_db.execute.side_effect = [
        MockUserResult(),
        MockDeptResult(),
    ]

    job_update = KekaJobDetailsUpdateRequest(
        jobTitle="Principal SRE",
        department="DevOps",
        location="Austin Office",
        noticePeriod="60 Days",
        shiftPolicy="General Shift",
    )

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "update_employee_job_details", new_callable=AsyncMock, return_value={"succeeded": True}) as mock_put:

        res = await KekaService.update_employee_job_details_flow(
            db=mock_db,
            payload=job_update,
            user_id=50,
        )

        assert res["success"] is True
        assert res["keka_employee_id"] == "keka-guid-50"
        mock_put.assert_awaited_once_with(
            employee_id="keka-guid-50",
            payload=job_update.model_dump(exclude_unset=True),
        )
        assert local_user.department_id == 9
        mock_db.commit.assert_awaited()


# =============================================================================
# 3. EMPLOYEE EXIT END-TO-END FUNCTIONAL FLOW
# =============================================================================


@pytest.mark.asyncio
async def test_create_employee_exit_flow_success():
    mock_db = AsyncMock()

    local_user = User(id=77, first_name="Exiting", last_name="Staff", status="Active")
    mapping = KekaEmployeeMapping(local_user_id=77, keka_employee_id="keka-guid-77", sync_status="active")

    class MockUserResult:
        def scalar_one_or_none(self):
            return local_user

    mock_db.execute.return_value = MockUserResult()

    exit_req = KekaEmployeeExitRequest(
        exitType=0,  # Resignation
        exitReason="Personal relocation",
        resignationDate="2026-10-01T00:00:00Z",
        lastWorkingDate="2026-11-01T00:00:00Z",
        isOkToRehire=True,
        comments="Eligible for future rehire",
    )

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "create_employee_exit_request", new_callable=AsyncMock, return_value={"data": True, "succeeded": True}) as mock_exit:

        res = await KekaService.create_employee_exit_flow(
            db=mock_db,
            payload=exit_req,
            user_id=77,
        )

        assert res["success"] is True
        assert res["keka_employee_id"] == "keka-guid-77"
        mock_exit.assert_awaited_once_with(
            employee_id="keka-guid-77",
            payload=exit_req.model_dump(exclude_unset=True),
        )
        assert local_user.status == "Inactive"
        assert mapping.sync_status == "inactive"
        mock_db.commit.assert_awaited()


# =============================================================================
# 4. ATTENDANCE TIME ENTRY FUNCTIONAL FLOW
# =============================================================================


@pytest.mark.asyncio
async def test_push_attendance_time_entry_flow_success():
    mock_db = AsyncMock()

    mapping = KekaEmployeeMapping(local_user_id=88, keka_employee_id="keka-guid-88")

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "log_attendance_time_entry", new_callable=AsyncMock, return_value={"succeeded": True}) as mock_time_entry:

        res = await KekaAttendanceService.push_time_entry_for_user(
            db=mock_db,
            user_id=88,
            timestamp=datetime(2026, 10, 6, 9, 0, 0),
            punch_status=1,  # In
            note="Morning Punch In",
        )

        assert res["success"] is True
        assert res["keka_employee_id"] == "keka-guid-88"
        mock_time_entry.assert_awaited_once_with(
            route_employee_id="keka-guid-88",
            timestamp="2026-10-06T09:00:00",
            punch_status=1,
            note="Morning Punch In",
        )


# =============================================================================
# 5. WORK FROM HOME & ON DUTY FUNCTIONAL FLOWS
# =============================================================================


@pytest.mark.asyncio
async def test_create_wfh_flow_success():
    mock_db = AsyncMock()

    mapping = KekaEmployeeMapping(local_user_id=99, keka_employee_id="keka-guid-99")

    wfh_req = KekaWFHCreateRequest(
        employeeId="placeholder",
        fromDate="2026-11-01T00:00:00Z",
        toDate="2026-11-02T00:00:00Z",
        fromSession=0,
        toSession=1,
        note="Remote project sprint",
    )

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "create_wfh_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": True}) as mock_wfh:

        res = await KekaService.create_wfh_flow(
            db=mock_db,
            payload=wfh_req,
            user_id=99,
        )

        assert res["success"] is True
        assert res["keka_employee_id"] == "keka-guid-99"
        sent = mock_wfh.await_args[0][0]
        assert sent["employeeId"] == "keka-guid-99"
        assert sent["fromDate"] == "2026-11-01T00:00:00Z"
        assert sent["note"] == "Remote project sprint"


@pytest.mark.asyncio
async def test_create_od_flow_success():
    mock_db = AsyncMock()

    mapping = KekaEmployeeMapping(local_user_id=99, keka_employee_id="keka-guid-99")

    od_req = KekaODCreateRequest(
        employeeId="placeholder",
        fromDate="2026-11-05T00:00:00Z",
        toDate="2026-11-05T00:00:00Z",
        fromSession=0,
        toSession=1,
        note="Client meeting at HQ",
    )

    with patch("app.modules.keka.repository.KekaEmployeeMappingRepository.get_by_local_user_id", new_callable=AsyncMock, return_value=mapping), \
         patch.object(KekaClient, "create_od_request", new_callable=AsyncMock, return_value={"succeeded": True, "data": True}) as mock_od:

        res = await KekaService.create_od_flow(
            db=mock_db,
            payload=od_req,
            user_id=99,
        )

        assert res["success"] is True
        assert res["keka_employee_id"] == "keka-guid-99"
        sent = mock_od.await_args[0][0]
        assert sent["employeeId"] == "keka-guid-99"
        assert sent["note"] == "Client meeting at HQ"
