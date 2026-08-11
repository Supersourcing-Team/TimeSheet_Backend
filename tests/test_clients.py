from unittest.mock import patch
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.modules.auth.jwt import create_access_token


client = TestClient(app)


class MockRole:
    def __init__(self, id=2, name="Project_Manager"):
        self.id = id
        self.name = name


class MockUser:
    def __init__(self, id=1, role_name="Project_Manager"):
        self.id = id
        self.role = MockRole(name=role_name)


def pm_auth_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def admin_auth_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


PM_USER = MockUser(id=1, role_name="Project_Manager")
ADMIN_USER = MockUser(id=2, role_name="Admin")


class MockClient:
    def __init__(self, id=1, name="Acme Corp", email="contact@acme.com", phone="1234567890", is_active=True):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.is_active = is_active
        self.created_at = datetime.now()


def test_create_client_pm_success():
    payload = {"name": "Acme Corp", "email": "contact@acme.com", "phone": "1234567890"}
    created_client = MockClient()

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.clients.service.ClientRepository.create", return_value=created_client):

        response = client.post("/api/v1/clients/", json=payload, headers=pm_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["name"] == "Acme Corp"


def test_create_client_admin_forbidden():
    payload = {"name": "Acme Corp"}
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER):
        response = client.post("/api/v1/clients/", json=payload, headers=admin_auth_headers())
        assert response.status_code == 403


def test_get_clients_success():
    clients_list = [MockClient(id=1, name="Client 1"), MockClient(id=2, name="Client 2")]
    
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.clients.service.ClientRepository.get_all", return_value=clients_list):

        response = client.get("/api/v1/clients/", headers=pm_auth_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert len(json_data["data"]) == 2
