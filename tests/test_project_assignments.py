from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token

client = TestClient(app)

class MockRole:
    def __init__(self, id=2, name="Project_Manager"):
        self.id = id
        self.name = name

class MockUser:
    def __init__(self, id=1, role_name="Project_Manager", status="Active"):
        self.id = id
        self.role = MockRole(name=role_name)
        self.status = status

class MockProject:
    def __init__(self, id=1, name="Project X"):
        self.id = id
        self.project_name = name

def pm_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}

def test_batch_project_assignment_success():
    pm = MockUser(id=1, role_name="Project_Manager")
    user1 = MockUser(id=10, role_name="Employee", status="Active")
    user2 = MockUser(id=11, role_name="Employee", status="Active")
    proj1 = MockProject(id=100)
    proj2 = MockProject(id=200)

    async def mock_get_proj(pid):
        return proj1 if pid == 100 else proj2

    async def mock_get_user(db, uid):
        return user1 if uid == 10 else user2

    async def mock_get_any(pid, uid):
        return None

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=pm), \
         patch("app.modules.projects.repository.ProjectRepository.get_by_id", side_effect=mock_get_proj), \
         patch("app.modules.users.repository.UserRepository.get_by_id", side_effect=mock_get_user), \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_any_assignment", side_effect=mock_get_any), \
         patch("sqlalchemy.ext.asyncio.AsyncSession.commit"):

        payload = {
            "project_ids": [100, 200],
            "user_ids": [10, 11]
        }
        response = client.post("/api/v1/project-assignments/batch", json=payload, headers=pm_headers())
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["assigned_count"] == 4
        assert data["reactivated_count"] == 0
        assert data["skipped_count"] == 0
        assert data["total_requested"] == 4
