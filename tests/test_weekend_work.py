from datetime import date, datetime
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
        self.first_name = "Test"
        self.last_name = "User"
        self.email = f"user{id}@test.com"
        self.employee_id = f"EMP00{id}"
        self.status = status
        self.role = MockRole(id=1 if role_name == "Admin" else (2 if role_name == "Project_Manager" else 4), name=role_name)


class MockProject:
    def __init__(self, id=10, project_manager_id=2):
        self.id = id
        self.project_manager_id = project_manager_id


class MockProjectAssignment:
    def __init__(self, id=1, project_id=10, user_id=1):
        self.id = id
        self.project_id = project_id
        self.user_id = user_id
        self.project = MockProject(id=project_id, project_manager_id=2)


class MockWeekendWorkRequest:
    def __init__(self, id=1, project_assignment_id=1, status="Pending", planned_hours=8.0):
        self.id = id
        self.project_assignment_id = project_assignment_id
        self.work_date = date(2026, 8, 15)  # Saturday
        self.planned_hours = planned_hours
        self.reason = "Urgent project deployment"
        self.status = status
        self.approved_by = None
        self.approved_at = None
        self.created_at = datetime(2026, 8, 11)
        self.project_assignment = MockProjectAssignment()
        self.approver = None



EMPLOYEE_USER = MockUser(id=1, role_name="Employee")
PM_USER = MockUser(id=2, role_name="Project_Manager")


def employee_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def pm_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test: POST /api/v1/weekend-work
# ---------------------------------------------------------------------------

def test_submit_weekend_work_success():
    payload = {
        "project_assignment_id": 1,
        "work_date": "2026-08-15",  # Saturday
        "reason": "Production release monitoring",
    }
    assignment = MockProjectAssignment()
    created_req = MockWeekendWorkRequest(id=1, status="Pending")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.weekend_work.validator.WeekendWorkValidator.validate_project_assignment", return_value=assignment), \
         patch("app.modules.weekend_work.repository.WeekendWorkRepository.get_by_assignment_and_date", return_value=None), \
         patch("app.modules.weekend_work.service.WeekendWorkRepository.create", return_value=created_req):

        response = client.post("/api/v1/weekend-work/", json=payload, headers=employee_headers())
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Pending"


def test_submit_weekend_work_rejected_for_regular_weekday():
    payload = {
        "project_assignment_id": 1,
        "work_date": "2026-08-12",  # Wednesday (Not a weekend or holiday)
        "reason": "Regular work",
    }
    assignment = MockProjectAssignment()

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER), \
         patch("app.modules.holidays.repository.HolidayRepository.get_by_date", return_value=None), \
         patch("app.modules.weekend_work.validator.WeekendWorkValidator.validate_project_assignment", return_value=assignment):

        response = client.post("/api/v1/weekend-work/", json=payload, headers=employee_headers())
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "only permitted on Saturdays, Sundays, or official public holidays" in data["message"]


# ---------------------------------------------------------------------------
# Test: PUT /api/v1/weekend-work/{id}/approve
# ---------------------------------------------------------------------------

def test_approve_weekend_work_by_pm_success():
    req = MockWeekendWorkRequest(id=1, status="Pending")
    approved_req = MockWeekendWorkRequest(id=1, status="Approved")

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=PM_USER), \
         patch("app.modules.weekend_work.service.WeekendWorkRepository.get_by_id", return_value=req), \
         patch("app.modules.weekend_work.service.WeekendWorkRepository.update_status", return_value=approved_req):

        response = client.put("/api/v1/weekend-work/1/approve", headers=pm_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "Approved"
