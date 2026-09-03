import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.model import User
from app.modules.roles.model import Role
from app.modules.auth.jwt import create_access_token, create_refresh_token
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import login_with_google, refresh_access_token

client = TestClient(app)


class MockRole:
    def __init__(self, id=1, name="Admin"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, email="test@example.com", status="Active", first_name="Test", last_name="User", employee_id="EMP001", role=None):
        self.id = id
        self.email = email
        self.status = status
        self.first_name = first_name
        self.last_name = last_name
        self.employee_id = employee_id
        self.role = role or MockRole()


@pytest.mark.asyncio
async def test_login_with_google_success():
    mock_idinfo = {"email": "test@example.com"}
    mock_user = MockUser(id=1, email="test@example.com", status="Active")

    with patch("app.modules.auth.service.verify_google_token", return_value=mock_idinfo), \
         patch("app.modules.auth.service.AuthRepository.get_user_by_email", return_value=mock_user):

        result = await login_with_google("valid_credential", db=None)

        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.user.email == "test@example.com"
        assert result.user.role == "Admin"


@pytest.mark.asyncio
async def test_login_with_google_unregistered_user():
    mock_idinfo = {"email": "unregistered@example.com"}

    with patch("app.modules.auth.service.verify_google_token", return_value=mock_idinfo), \
         patch("app.modules.auth.service.AuthRepository.get_user_by_email", return_value=None):

        with pytest.raises(Exception) as exc_info:
            await login_with_google("valid_credential", db=None)

        assert exc_info.value.status_code == 404
        assert "User not registered" in exc_info.value.detail


@pytest.mark.asyncio
async def test_login_with_google_deactivated_user():
    mock_idinfo = {"email": "inactive@example.com"}
    mock_user = MockUser(id=2, email="inactive@example.com", status="Inactive")

    with patch("app.modules.auth.service.verify_google_token", return_value=mock_idinfo), \
         patch("app.modules.auth.service.AuthRepository.get_user_by_email", return_value=mock_user):

        with pytest.raises(Exception) as exc_info:
            await login_with_google("valid_credential", db=None)

        assert exc_info.value.status_code == 403
        assert "deactivated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_token_success():
    mock_user = MockUser(id=1, email="test@example.com", status="Active")
    refresh_token_str = create_refresh_token(data={"sub": "1"})

    with patch("app.modules.auth.service.AuthRepository.get_user_by_id", return_value=mock_user):
        result = await refresh_access_token(refresh_token_str, db=None)

        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.user.id == 1


def test_logout_endpoint():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert "logged out" in json_data["message"]


def test_google_login_endpoint_success():
    mock_idinfo = {"email": "test@example.com"}
    mock_user = MockUser(id=1, email="test@example.com", status="Active")

    with patch("app.modules.auth.service.verify_google_token", return_value=mock_idinfo), \
         patch("app.modules.auth.service.AuthRepository.get_user_by_email", return_value=mock_user):

        response = client.post("/api/v1/auth/google/login", json={"credential": "mock_google_token"})
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["message"] == "Login successful"
        assert json_data["data"]["access_token"] is not None
        assert json_data["data"]["refresh_token"] is not None
        assert json_data["data"]["user"]["email"] == "test@example.com"


def test_google_login_endpoint_unregistered():
    mock_idinfo = {"email": "notfound@example.com"}

    with patch("app.modules.auth.service.verify_google_token", return_value=mock_idinfo), \
         patch("app.modules.auth.service.AuthRepository.get_user_by_email", return_value=None):

        response = client.post("/api/v1/auth/google/login", json={"credential": "mock_google_token"})
        assert response.status_code == 404
        json_data = response.json()
        assert json_data["success"] is False
        assert "User not registered" in json_data["message"]


def test_get_me_endpoint_success():
    mock_user = MockUser(id=1, email="test@example.com", status="Active")
    access_token_str = create_access_token(data={"sub": "1"})

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=mock_user):
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token_str}"})
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["email"] == "test@example.com"
        assert json_data["data"]["role"] == "Admin"

