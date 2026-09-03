from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.model import User
from app.modules.roles.model import Role
from app.modules.auth.jwt import create_access_token


client = TestClient(app)


# ---------------------------------------------------------------------------
# Shared Mocks
# ---------------------------------------------------------------------------

class MockRole:
    def __init__(self, id=1, name="Admin", description="System administrator", created_at=None):
        from datetime import datetime
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at or datetime(2024, 1, 1)


class MockUser:
    def __init__(
        self,
        id=1,
        email="admin@test.com",
        status="Active",
        first_name="Test",
        last_name="Admin",
        employee_id="EMP001",
        role_id=1,
        role=None,
        joining_date=None,
        created_at=None,
        updated_at=None,
    ):
        from datetime import datetime
        self.id = id
        self.email = email
        self.status = status
        self.first_name = first_name
        self.last_name = last_name
        self.employee_id = employee_id
        self.role_id = role_id
        self.role = role or MockRole()
        self.joining_date = joining_date
        self.created_at = created_at or datetime(2024, 1, 1)
        self.updated_at = updated_at or datetime(2024, 1, 1)


def admin_auth_headers():
    """Generate valid Admin Bearer token headers for endpoint tests."""
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def employee_auth_headers():
    """Generate valid Employee Bearer token headers (no admin access)."""
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


ADMIN_USER = MockUser(id=1, email="admin@test.com", role=MockRole(id=1, name="Admin"))
EMPLOYEE_USER = MockUser(
    id=2,
    email="employee@test.com",
    employee_id="EMP002",
    role=MockRole(id=4, name="Employee"),
)


# ---------------------------------------------------------------------------
# Test: GET /api/v1/roles
# ---------------------------------------------------------------------------

def test_list_roles_success():
    roles = [
        MockRole(id=1, name="Admin"),
        MockRole(id=2, name="Project_Manager"),
        MockRole(id=3, name="Account_Manager"),
        MockRole(id=4, name="Employee"),
    ]
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.roles.service.RoleRepository.list_roles", return_value=roles):

        response = client.get("/api/v1/roles", headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert len(json_data["data"]) == 4
        assert json_data["data"][0]["name"] == "Admin"


def test_list_roles_requires_auth():
    response = client.get("/api/v1/roles")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: POST /api/v1/users — Admin creates a user
# ---------------------------------------------------------------------------

def test_create_user_admin_success():
    new_user_payload = {
        "email": "newemployee@test.com",
        "first_name": "John",
        "last_name": "Doe",
        "employee_id": "EMP003",
        "role_id": 4,
        "joining_date": "2024-01-15",
        "status": "Active",
    }
    created_user = MockUser(
        id=3,
        email="newemployee@test.com",
        first_name="John",
        last_name="Doe",
        employee_id="EMP003",
        role_id=4,
        role=MockRole(id=4, name="Employee"),
    )

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.RoleRepository.get_by_id", return_value=MockRole(id=4, name="Employee")), \
         patch("app.modules.users.service.UserRepository.get_by_email", return_value=None), \
         patch("app.modules.users.service.UserRepository.get_by_employee_id", return_value=None), \
         patch("app.modules.users.service.UserRepository.create", return_value=created_user):

        response = client.post("/api/v1/users", json=new_user_payload, headers=admin_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["email"] == "newemployee@test.com"
        assert json_data["data"]["role"]["name"] == "Employee"


def test_create_user_duplicate_email_rejected():
    payload = {
        "email": "admin@test.com",  # Already exists
        "first_name": "John",
        "last_name": "Doe",
        "employee_id": "EMP099",
        "role_id": 4,
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.RoleRepository.get_by_id", return_value=MockRole(id=4, name="Employee")), \
         patch("app.modules.users.service.UserRepository.get_by_email", return_value=ADMIN_USER):

        response = client.post("/api/v1/users", json=payload, headers=admin_auth_headers())
        assert response.status_code == 409
        json_data = response.json()
        assert json_data["success"] is False
        assert "already exists" in json_data["message"]


def test_create_user_non_admin_forbidden():
    payload = {
        "email": "someone@test.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "employee_id": "EMP010",
        "role_id": 4,
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.post("/api/v1/users", json=payload, headers=employee_auth_headers())
        assert response.status_code == 403
        json_data = response.json()
        assert json_data["success"] is False


# ---------------------------------------------------------------------------
# Test: GET /api/v1/users — Paginated listing
# ---------------------------------------------------------------------------

def test_list_users_success():
    users_list = [ADMIN_USER, EMPLOYEE_USER]
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.UserRepository.list_users", return_value=(users_list, 2)):

        response = client.get("/api/v1/users", headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["total"] == 2
        assert len(json_data["data"]["items"]) == 2


def test_list_users_with_search_filter():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.UserRepository.list_users", return_value=([EMPLOYEE_USER], 1)):

        response = client.get("/api/v1/users?search=John&status=Active", headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["total"] == 1


# ---------------------------------------------------------------------------
# Test: GET /api/v1/users/{id}
# ---------------------------------------------------------------------------

def test_get_user_by_id_success():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.UserRepository.get_by_id", return_value=EMPLOYEE_USER):

        response = client.get("/api/v1/users/2", headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["id"] == 2


def test_get_user_by_id_not_found():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.UserRepository.get_by_id", return_value=None):

        response = client.get("/api/v1/users/999", headers=admin_auth_headers())
        assert response.status_code == 404
        json_data = response.json()
        assert json_data["success"] is False


# ---------------------------------------------------------------------------
# Test: PATCH /api/v1/users/{id}/status — Soft delete
# ---------------------------------------------------------------------------

def test_toggle_user_status_to_inactive():
    deactivated_user = MockUser(id=2, email="employee@test.com", status="Inactive", role=MockRole(id=4, name="Employee"))

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch("app.modules.users.service.UserRepository.get_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.users.service.UserRepository.toggle_status", return_value=deactivated_user):

        response = client.patch("/api/v1/users/2/status", json={"status": "Inactive"}, headers=admin_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["status"] == "Inactive"


def test_toggle_user_status_non_admin_forbidden():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        response = client.patch("/api/v1/users/1/status", json={"status": "Inactive"}, headers=employee_auth_headers())
        assert response.status_code == 403
