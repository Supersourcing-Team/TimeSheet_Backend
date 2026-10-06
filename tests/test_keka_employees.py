from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.keka.schema import KekaEmployeeResponse
from app.services.keka.keka_auth import KekaAuthManager
from app.services.keka.keka_client import KekaAPIError, KekaClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Mocks & Helpers
# ---------------------------------------------------------------------------

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


MOCK_KEKA_EMPLOYEE_1 = {
    "id": "emp-uuid-1",
    "employeeNumber": "EMP001",
    "firstName": "John",
    "lastName": "Doe",
    "displayName": "John Doe",
    "email": "john.doe@company.com",
    "department": {"id": "dept-1", "name": "Engineering"},
    "jobTitle": "Senior Software Engineer",
    "dateOfJoining": "2022-04-01T00:00:00Z",
    "employmentStatus": "Working",
}

MOCK_KEKA_EMPLOYEE_2 = {
    "id": "emp-uuid-2",
    "employeeNumber": "EMP002",
    "firstName": "Jane",
    "lastName": "Smith",
    "displayName": "Jane Smith",
    "email": "jane.smith@company.com",
    "department": "Product Management",
    "jobTitle": "Product Manager",
    "dateOfJoining": "2023-01-15T00:00:00Z",
    "employmentStatus": 0,  # Integer enum for "Working"
}


# ---------------------------------------------------------------------------
# 1. Schema Normalization Tests
# ---------------------------------------------------------------------------

def test_keka_employee_schema_normalization():
    # Test normalization of dict department and string employmentStatus
    emp1 = KekaEmployeeResponse.model_validate(MOCK_KEKA_EMPLOYEE_1)
    assert emp1.id == "emp-uuid-1"
    assert emp1.department == "Engineering"
    assert emp1.status == "Working"
    assert emp1.displayName == "John Doe"

    # Test normalization of int enum employmentStatus and string department
    emp2 = KekaEmployeeResponse.model_validate(MOCK_KEKA_EMPLOYEE_2)
    assert emp2.id == "emp-uuid-2"
    assert emp2.department == "Product Management"
    assert emp2.status == "Working"


def test_keka_employee_schema_missing_fields():
    minimal_data = {"id": "min-1"}
    emp = KekaEmployeeResponse.model_validate(minimal_data)
    assert emp.id == "min-1"
    assert emp.employeeNumber is None
    assert emp.email is None
    assert emp.status is None


# ---------------------------------------------------------------------------
# 2. Client Tests: Single Page & Multi-page Pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_employees_single_page():
    mock_payload = {
        "pageNumber": 1,
        "pageSize": 100,
        "totalRecords": 2,
        "totalPages": 1,
        "data": [MOCK_KEKA_EMPLOYEE_1, MOCK_KEKA_EMPLOYEE_2],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):

        result = await KekaClient.get_employees(page_number=1, page_size=100)

        assert result["pageNumber"] == 1
        assert result["pageSize"] == 100
        assert result["totalRecords"] == 2
        assert result["totalPages"] == 1
        assert len(result["data"]) == 2
        assert result["data"][0]["employeeNumber"] == "EMP001"


@pytest.mark.asyncio
async def test_get_all_employees_multiple_pages():
    page_1_payload = {
        "pageNumber": 1,
        "pageSize": 2,
        "totalRecords": 3,
        "totalPages": 2,
        "data": [MOCK_KEKA_EMPLOYEE_1, MOCK_KEKA_EMPLOYEE_2],
    }

    page_2_payload = {
        "pageNumber": 2,
        "pageSize": 2,
        "totalRecords": 3,
        "totalPages": 2,
        "data": [{
            "id": "emp-uuid-3",
            "employeeNumber": "EMP003",
            "firstName": "Alice",
            "lastName": "Brown",
            "email": "alice@company.com",
        }],
    }

    resp1 = MagicMock(status_code=200, json=MagicMock(return_value=page_1_payload))
    resp2 = MagicMock(status_code=200, json=MagicMock(return_value=page_2_payload))

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=[resp1, resp2]):

        result = await KekaClient.get_all_employees(page_size=2)

        assert result["totalRecords"] == 3
        assert result["totalPagesRetrieved"] == 2
        assert len(result["data"]) == 3
        assert result["data"][2]["employeeNumber"] == "EMP003"


@pytest.mark.asyncio
async def test_get_employees_empty_response():
    empty_payload = {
        "pageNumber": 1,
        "pageSize": 100,
        "totalRecords": 0,
        "totalPages": 0,
        "data": [],
    }
    mock_resp = MagicMock(status_code=200, json=MagicMock(return_value=empty_payload))

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_resp):

        result = await KekaClient.get_employees(page_number=1, page_size=100)
        assert result["totalRecords"] == 0
        assert result["totalPages"] == 0
        assert result["data"] == []


# ---------------------------------------------------------------------------
# 3. Client Tests: 401, 403, 429, and Malformed Responses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keka_401_retry_success():
    resp_401 = MagicMock(status_code=401, text="Unauthorized")
    resp_200 = MagicMock(status_code=200, json=MagicMock(return_value={"data": []}))

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, side_effect=["old_token", "new_token"]) as mock_auth, \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=[resp_401, resp_200]):

        result = await KekaClient.get("/hris/employees")
        assert result == {"data": []}
        # Auth token was refreshed on second attempt
        assert mock_auth.call_count == 2
        mock_auth.assert_called_with(force_refresh=True)


@pytest.mark.asyncio
async def test_keka_401_retry_failure():
    resp_401_1 = MagicMock(status_code=401, text="Unauthorized")
    resp_401_2 = MagicMock(status_code=401, text="Unauthorized")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=[resp_401_1, resp_401_2]):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.get("/hris/employees")

        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_keka_403_forbidden():
    resp_403 = MagicMock(status_code=403, text="Forbidden")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_403):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.get("/hris/employees")

        assert exc_info.value.status_code == 403
        assert "forbidden" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_keka_429_rate_limit():
    resp_429 = MagicMock(status_code=429, text="Too Many Requests")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_429):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.get("/hris/employees")

        assert exc_info.value.status_code == 429
        assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_keka_malformed_response():
    resp_bad = MagicMock(status_code=200)
    resp_bad.json.side_effect = ValueError("Invalid JSON string")

    with patch.object(KekaAuthManager, "get_access_token", new_callable=AsyncMock, return_value="mock_token"), \
         patch.object(KekaClient, "get_base_url", return_value="https://test.keka.com/api/v1"), \
         patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=resp_bad):

        with pytest.raises(KekaAPIError) as exc_info:
            await KekaClient.get("/hris/employees")

        assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# 4. HTTP API Endpoints Tests
# ---------------------------------------------------------------------------

def test_api_get_employees_endpoint_success():
    mock_service_result = {
        "pageNumber": 1,
        "pageSize": 10,
        "totalRecords": 2,
        "totalPages": 1,
        "data": [MOCK_KEKA_EMPLOYEE_1, MOCK_KEKA_EMPLOYEE_2],
    }

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_employees", new_callable=AsyncMock, return_value=mock_service_result):

        response = client.get("/api/v1/keka/employees?pageNumber=1&pageSize=10", headers=admin_headers())

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["pageNumber"] == 1
        assert json_data["data"]["totalRecords"] == 2
        assert len(json_data["data"]["data"]) == 2
        assert json_data["data"]["data"][0]["displayName"] == "John Doe"
        assert json_data["data"]["data"][0]["department"] == "Engineering"


def test_api_get_all_employees_endpoint_success():
    mock_all_result = {
        "totalRecords": 2,
        "totalPagesRetrieved": 1,
        "data": [MOCK_KEKA_EMPLOYEE_1, MOCK_KEKA_EMPLOYEE_2],
    }

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_all_employees", new_callable=AsyncMock, return_value=mock_all_result):

        response = client.get("/api/v1/keka/employees/all", headers=admin_headers())

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["totalRecords"] == 2
        assert json_data["data"]["totalPagesRetrieved"] == 1
        assert len(json_data["data"]["data"]) == 2


def test_api_get_employees_forbidden_for_non_admin():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.get("/api/v1/keka/employees", headers=employee_headers())
        assert response.status_code == 403


def test_api_error_does_not_leak_secrets():
    # Simulate a Keka API error
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaClient, "get_employees", new_callable=AsyncMock, side_effect=KekaAPIError("Upstream failure", status_code=502)):

        response = client.get("/api/v1/keka/employees", headers=admin_headers())
        assert response.status_code == 502
        body_text = response.text.lower()
        # Verify no credentials leaked
        assert "client_secret" not in body_text
        assert "api_key" not in body_text
        assert "access_token" not in body_text
