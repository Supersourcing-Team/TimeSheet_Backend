from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.keka.service import KekaEmployeeMappingService
from app.services.keka.keka_client import KekaClient

client = TestClient(app)


class MockRole:
    def __init__(self, id=1, name="Admin"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, email="admin@test.com", role_name="Admin"):
        self.id = id
        self.email = email
        self.status = "Active"
        self.role = MockRole(name=role_name)


ADMIN_USER = MockUser(id=1, email="admin@test.com", role_name="Admin")
EMPLOYEE_USER = MockUser(id=2, email="user@test.com", role_name="Employee")


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def employee_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# CATEGORY 1 – HR CORE & EMPLOYEE LIFECYCLE TESTS
# =============================================================================


def test_get_employee_details_endpoint():
    mock_data = {"id": "emp-uuid-1", "firstName": "John", "lastName": "Doe", "displayName": "John Doe"}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_employee", new_callable=AsyncMock, return_value=mock_data):

        response = client.get("/api/v1/keka/employees/emp-uuid-1", headers=admin_headers())
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["data"]["id"] == "emp-uuid-1"
        assert res["data"]["displayName"] == "John Doe"


def test_create_employee_endpoint():
    mock_result = {"success": True, "keka_employee_id": "new-emp-uuid-123", "data": "new-emp-uuid-123"}
    payload = {
        "firstName": "Alice",
        "lastName": "Smith",
        "email": "alice.smith@example.com",
        "dateJoined": "2026-01-01T00:00:00Z"
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "create_employee_flow", new_callable=AsyncMock, return_value=mock_result):

        response = client.post("/api/v1/keka/employees", json=payload, headers=admin_headers())
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["data"]["keka_employee_id"] == "new-emp-uuid-123"


def test_get_departments_endpoint():
    mock_depts = {"data": [{"id": "d-1", "name": "Engineering"}], "totalRecords": 1}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_departments", new_callable=AsyncMock, return_value=mock_depts):

        response = client.get("/api/v1/keka/departments?pageNumber=1&pageSize=10", headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["totalRecords"] == 1


def test_get_job_titles_endpoint():
    mock_titles = {"data": [{"id": "jt-1", "name": "Software Engineer"}], "totalRecords": 1}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_job_titles", new_callable=AsyncMock, return_value=mock_titles):

        response = client.get("/api/v1/keka/job-titles", headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["totalRecords"] == 1


def test_get_locations_endpoint():
    mock_locs = {"data": [{"id": "loc-1", "name": "Headquarters"}], "totalRecords": 1}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_locations", new_callable=AsyncMock, return_value=mock_locs):

        response = client.get("/api/v1/keka/locations", headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["totalRecords"] == 1


def test_get_groups_and_group_types():
    mock_groups = {"data": [{"id": "grp-1", "name": "Tech"}], "totalRecords": 1}
    mock_gtypes = {"data": [{"id": "gt-1", "name": "Departmental"}], "totalRecords": 1}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_groups", new_callable=AsyncMock, return_value=mock_groups), \
         patch.object(KekaClient, "get_group_types", new_callable=AsyncMock, return_value=mock_gtypes):

        r1 = client.get("/api/v1/keka/groups", headers=admin_headers())
        r2 = client.get("/api/v1/keka/group-types", headers=admin_headers())
        assert r1.status_code == 200
        assert r2.status_code == 200


def test_get_currencies_notice_periods_exit_reasons():
    mock_currencies = {"data": [{"id": "cur-1", "code": "USD"}]}
    mock_np = {"data": [{"id": "np-1", "name": "30 Days"}]}
    mock_er = {"data": [{"id": "er-1", "name": "Career Growth"}]}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_currencies", new_callable=AsyncMock, return_value=mock_currencies), \
         patch.object(KekaClient, "get_notice_periods", new_callable=AsyncMock, return_value=mock_np), \
         patch.object(KekaClient, "get_exit_reasons", new_callable=AsyncMock, return_value=mock_er):

        assert client.get("/api/v1/keka/currencies", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/notice-periods", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/exit-reasons", headers=admin_headers()).status_code == 200


def test_update_employee_job_details():
    mock_result = {"success": True, "keka_employee_id": "emp-uuid-1", "message": "Updated"}
    payload = {"department": "Engineering", "jobTitle": "Lead Engineer"}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "update_employee_job_details_flow", new_callable=AsyncMock, return_value=mock_result):

        response = client.put("/api/v1/keka/employees/emp-uuid-1/job-details", json=payload, headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["success"] is True


def test_employee_exit_request():
    mock_result = {"success": True, "keka_employee_id": "emp-uuid-1", "message": "Exit requested"}
    payload = {"exitType": 0, "resignationDate": "2026-06-01T00:00:00Z", "comments": "Relocating"}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "create_employee_exit_flow", new_callable=AsyncMock, return_value=mock_result):

        response = client.post("/api/v1/keka/employees/emp-uuid-1/exit-request", json=payload, headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["success"] is True


def test_get_contingent_types_and_update_fields():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_contingent_types", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_employee_update_fields", new_callable=AsyncMock, return_value={"data": []}):

        assert client.get("/api/v1/keka/contingent-types", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/employees/update-fields", headers=admin_headers()).status_code == 200


# =============================================================================
# CATEGORY 2 – EMPLOYEE DOCUMENTS TESTS
# =============================================================================


def test_document_endpoints():
    mock_types = {"data": [{"id": "dt-1", "name": "Passport"}]}
    mock_docs = {"data": [{"id": "doc-1", "fileName": "passport.pdf"}]}
    mock_att = {"data": "https://download.keka.com/doc-1"}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_document_types", new_callable=AsyncMock, return_value=mock_types), \
         patch.object(KekaClient, "get_employee_documents", new_callable=AsyncMock, return_value=mock_docs), \
         patch.object(KekaClient, "get_document_attachment_url", new_callable=AsyncMock, return_value=mock_att):

        r1 = client.get("/api/v1/keka/documents/types", headers=admin_headers())
        r2 = client.get("/api/v1/keka/employees/emp-uuid-1/documents", headers=admin_headers())
        r3 = client.get("/api/v1/keka/employees/emp-uuid-1/documents/doc-1/attachment", headers=admin_headers())

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200
        assert r3.json()["data"]["data"] == "https://download.keka.com/doc-1"


# =============================================================================
# CATEGORY 3 – LEAVE MANAGEMENT TESTS
# =============================================================================


def test_leave_balances_plans_and_requests_endpoints():
    mock_bal = {"data": [{"employeeId": "emp-uuid-1", "availableBalance": 12.0}]}
    mock_plans = {"data": [{"id": "lp-1", "name": "Standard Leave Plan"}]}
    mock_reqs = {"data": [{"id": "lr-1", "status": "Approved"}]}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_leave_balances", new_callable=AsyncMock, return_value=mock_bal), \
         patch.object(KekaClient, "get_leave_plans", new_callable=AsyncMock, return_value=mock_plans), \
         patch.object(KekaClient, "get_leave_requests", new_callable=AsyncMock, return_value=mock_reqs):

        r1 = client.get("/api/v1/keka/leave-balances?employeeIds=emp-uuid-1", headers=admin_headers())
        r2 = client.get("/api/v1/keka/leave-plans", headers=admin_headers())
        r3 = client.get("/api/v1/keka/leave-requests?from=2026-01-01&to=2026-01-31", headers=admin_headers())

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200


# =============================================================================
# CATEGORY 5 – ATTENDANCE TIME ENTRY TESTS
# =============================================================================


def test_create_attendance_time_entry_endpoint():
    mock_result = {"succeeded": True, "data": "entry-id-123"}
    payload = {
        "timestamp": "2026-05-15T09:00:00Z",
        "punchStatus": 0,
        "premiseName": "Office HQ"
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "create_attendance_time_entry", new_callable=AsyncMock, return_value=mock_result):

        response = client.post("/api/v1/keka/attendance/employees/emp-uuid-1/timeentry", json=payload, headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["data"]["data"] == "entry-id-123"


# =============================================================================
# CATEGORY 6 TO 11 – POLICIES, SCHEMES, CALENDARS, REGULARISATION
# =============================================================================


def test_policies_and_calendars_endpoints():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_weekly_off_policies", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_shift_policies", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_capture_schemes", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_holiday_calendars", new_callable=AsyncMock, return_value={"data": [{"id": "cal-1"}]}), \
         patch.object(KekaClient, "get_calendar_holidays", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_regularisation_requests", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaClient, "get_penalisation_policies", new_callable=AsyncMock, return_value={"data": []}):

        assert client.get("/api/v1/keka/weekly-off-policies", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/shift-policies", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/capture-scheme", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/holiday-calendars", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/holiday-calendars/cal-1/holidays", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/regularisation-requests", headers=admin_headers()).status_code == 200
        assert client.get("/api/v1/keka/penalisation-policies", headers=admin_headers()).status_code == 200


# =============================================================================
# CATEGORY 12 & 13 – WFH AND ON DUTY TESTS
# =============================================================================


def test_wfh_and_od_endpoints():
    mock_flow_wfh = {"success": True, "keka_employee_id": "emp-uuid-1", "message": "WFH submitted"}
    mock_flow_od = {"success": True, "keka_employee_id": "emp-uuid-1", "message": "OD submitted"}
    wfh_payload = {
        "employeeId": "emp-uuid-1",
        "fromDate": "2026-06-10T00:00:00Z",
        "toDate": "2026-06-11T00:00:00Z",
        "fromSession": 0,
        "toSession": 1,
        "note": "Working remotely"
    }
    od_payload = {
        "employeeId": "emp-uuid-1",
        "fromDate": "2026-06-12T00:00:00Z",
        "toDate": "2026-06-12T00:00:00Z",
        "fromSession": 0,
        "toSession": 1,
        "note": "Client visit"
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_wfh_requests", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaEmployeeMappingService, "create_wfh_flow", new_callable=AsyncMock, return_value=mock_flow_wfh), \
         patch.object(KekaClient, "get_od_requests", new_callable=AsyncMock, return_value={"data": []}), \
         patch.object(KekaEmployeeMappingService, "create_od_flow", new_callable=AsyncMock, return_value=mock_flow_od):

        assert client.get("/api/v1/keka/wfh", headers=admin_headers()).status_code == 200
        r_wfh = client.post("/api/v1/keka/wfh", json=wfh_payload, headers=admin_headers())
        assert r_wfh.status_code == 200
        assert r_wfh.json()["data"]["success"] is True

        assert client.get("/api/v1/keka/od", headers=admin_headers()).status_code == 200
        r_od = client.post("/api/v1/keka/od", json=od_payload, headers=admin_headers())
        assert r_od.status_code == 200
        assert r_od.json()["data"]["success"] is True



def test_extended_endpoints_forbidden_for_non_admin():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        assert client.get("/api/v1/keka/departments", headers=employee_headers()).status_code == 403
        assert client.get("/api/v1/keka/leave-balances", headers=employee_headers()).status_code == 403
        assert client.get("/api/v1/keka/wfh", headers=employee_headers()).status_code == 403
        assert client.get("/api/v1/keka/od", headers=employee_headers()).status_code == 403
