from unittest.mock import patch, AsyncMock
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


PM_USER = MockUser(id=1, role_name="Project_Manager")


class MockProject:
    def __init__(self, id=1, client_id=1, pm_id=1, name="Project X", budget=1000):
        self.id = id
        self.client_id = client_id
        self.project_manager_id = pm_id
        self.project_name = name
        self.budget = budget
        self.description = "Test project"
        self.start_date = None
        self.end_date = None
        self.status = "Planning"
        self.is_active = True
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


def test_create_project_pm_success():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project X",
        "budget": 1000.50
    }
    created_project = MockProject(budget=1000.50)

    # Need to mock the service layer completely to avoid DB validation calls,
    # OR mock the individual repository calls. Let's mock repository calls.
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.clients.repository.ClientRepository.get_by_id", return_value=True), \
         patch("app.modules.users.repository.UserRepository.get_by_id", return_value=PM_USER), \
         patch("app.modules.projects.repository.ProjectRepository.create", return_value=created_project), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.create", return_value=True), \
         patch("app.modules.projects.repository.ProjectRepository.get_by_id", return_value=created_project):

        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        assert response.status_code == 201
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["project_name"] == "Project X"
        assert json_data["data"]["budget"] == 1000.50



def test_create_project_invalid_dates():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project Y",
        "start_date": "2024-12-01",
        "end_date": "2024-11-01"  # End date before start date
    }
    
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        # Should fail Pydantic validation (422)
        assert response.status_code == 422


def test_create_project_invalid_budget():
    payload = {
        "client_id": 1,
        "project_manager_id": 1,
        "project_name": "Project Z",
        "budget": -50  # Negative budget
    }
    
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER):
        response = client.post("/api/v1/projects/", json=payload, headers=pm_auth_headers())
        # Should fail Pydantic validation (422)
        assert response.status_code == 422
