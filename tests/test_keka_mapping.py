from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.jwt import create_access_token
from app.modules.keka.model import KekaEmployeeMapping
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.keka.schema import KekaEmployeeMappingResponse
from app.modules.keka.service import KekaEmployeeMappingService
from app.modules.roles.model import Role
from app.modules.users.model import User
from app.services.keka.keka_client import KekaClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers & Models
# ---------------------------------------------------------------------------

def make_test_user(id=1, email="admin@test.com", employee_id="EMP001", first_name="Admin", last_name="User", role_name="Admin"):
    u = User(
        id=id,
        email=email,
        employee_id=employee_id,
        first_name=first_name,
        last_name=last_name,
        role_id=1,
        status="Active",
    )
    u.role = Role(id=1, name=role_name)
    return u


ADMIN_USER = make_test_user(id=1, email="admin@test.com", role_name="Admin")
EMPLOYEE_USER = make_test_user(id=2, email="user@test.com", role_name="Employee")


def admin_headers():
    token = create_access_token(data={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}


def employee_headers():
    token = create_access_token(data={"sub": "2"})
    return {"Authorization": f"Bearer {token}"}


def make_mock_mapping(
    id=1,
    keka_employee_id="keka-uuid-1",
    local_user_id=1,
    keka_employee_number="EMP001",
    sync_status="active",
    user=None,
):
    target_user = user or ADMIN_USER
    mapping = KekaEmployeeMapping(
        id=id,
        keka_employee_id=keka_employee_id,
        local_user_id=local_user_id,
        keka_employee_number=keka_employee_number,
        sync_status=sync_status,
        created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    mapping.user = target_user
    return mapping


# ---------------------------------------------------------------------------
# 1. Repository Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repository_get_by_keka_id():
    mock_db = AsyncMock()
    mock_mapping = make_mock_mapping()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_mapping
    mock_db.execute.return_value = mock_result

    res = await KekaEmployeeMappingRepository.get_by_keka_employee_id(mock_db, "keka-uuid-1")
    assert res is not None
    assert res.keka_employee_id == "keka-uuid-1"
    assert res.local_user_id == 1


@pytest.mark.asyncio
async def test_repository_get_by_local_user_id():
    mock_db = AsyncMock()
    mock_mapping = make_mock_mapping()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_mapping
    mock_db.execute.return_value = mock_result

    res = await KekaEmployeeMappingRepository.get_by_local_user_id(mock_db, 1)
    assert res is not None
    assert res.local_user_id == 1


@pytest.mark.asyncio
async def test_repository_create_and_update():
    mock_db = AsyncMock()
    mock_mapping = make_mock_mapping()

    with patch.object(KekaEmployeeMappingRepository, "get_by_keka_employee_id", new_callable=AsyncMock, return_value=mock_mapping):
        created = await KekaEmployeeMappingRepository.create_mapping(
            mock_db,
            keka_employee_id="keka-uuid-1",
            local_user_id=1,
            keka_employee_number="EMP001",
        )
        assert mock_db.add.called
        assert mock_db.commit.called
        assert created.keka_employee_id == "keka-uuid-1"

    updated = await KekaEmployeeMappingRepository.update_mapping(
        mock_db, mock_mapping, sync_status="inactive"
    )
    assert updated.sync_status == "inactive"
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_repository_list_mappings():
    mock_db = AsyncMock()
    user2 = make_test_user(id=2, email="user2@test.com")
    mock_mappings = [
        make_mock_mapping(id=1),
        make_mock_mapping(id=2, keka_employee_id="keka-uuid-2", local_user_id=2, user=user2),
    ]

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = mock_mappings

    mock_db.execute.side_effect = [count_result, items_result]

    items, total = await KekaEmployeeMappingRepository.list_mappings(mock_db, skip=0, limit=10)
    assert total == 2
    assert len(items) == 2


# ---------------------------------------------------------------------------
# 2. Schema Tests
# ---------------------------------------------------------------------------

def test_keka_employee_mapping_response_schema():
    mapping = make_mock_mapping()
    schema = KekaEmployeeMappingResponse.model_validate(mapping)
    assert schema.id == 1
    assert schema.keka_employee_id == "keka-uuid-1"
    assert schema.local_user_id == 1
    assert schema.local_user_email == "admin@test.com"
    assert schema.local_user_name == "Admin User"


# ---------------------------------------------------------------------------
# 3. Mapping Preview Logic Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mapping_preview_classification():
    """
    Tests all 4 classifications in one comprehensive preview:
    1. Employee 1: 'mapped' (already in mapping table)
    2. Employee 2: 'local_match' (matches by email)
    3. Employee 3: 'local_match' (matches by employeeNumber)
    4. Employee 4: 'unmapped' (no match)
    5. Employee 5: 'conflict' (email matches user A, but emp number matches user B)
    """
    user_1 = make_test_user(id=1, email="john@company.com", employee_id="EMP001", first_name="John", last_name="Doe")
    user_2 = make_test_user(id=2, email="jane@company.com", employee_id="EMP002", first_name="Jane", last_name="Smith")
    user_3 = make_test_user(id=3, email="bob.diff@company.com", employee_id="EMP003", first_name="Bob", last_name="Taylor")
    user_4 = make_test_user(id=4, email="clash.email@company.com", employee_id="EMP004", first_name="Clash", last_name="Email")
    user_5 = make_test_user(id=5, email="clash.other@company.com", employee_id="EMP005", first_name="Clash", last_name="Num")

    existing_mapping = make_mock_mapping(
        id=1,
        keka_employee_id="keka-uuid-1",
        local_user_id=1,
        keka_employee_number="EMP001",
        user=user_1,
    )

    keka_api_employees = [
        # 1. Already mapped
        {"id": "keka-uuid-1", "email": "john@company.com", "employeeNumber": "EMP001", "displayName": "John Doe"},
        # 2. Match by email
        {"id": "keka-uuid-2", "email": "jane@company.com", "employeeNumber": "KEKA-NEW-02", "displayName": "Jane Smith"},
        # 3. Match by employee number
        {"id": "keka-uuid-3", "email": "bob.keka@company.com", "employeeNumber": "EMP003", "displayName": "Bob Taylor"},
        # 4. Completely unmapped
        {"id": "keka-uuid-4", "email": "stranger@company.com", "employeeNumber": "EMP999", "displayName": "Stranger"},
        # 5. Conflict (email matches user_4, emp number matches user_5)
        {"id": "keka-uuid-5", "email": "clash.email@company.com", "employeeNumber": "EMP005", "displayName": "Clash User"},
    ]

    mock_db = AsyncMock()
    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user_1, user_2, user_3, user_4, user_5]
    mappings_result = MagicMock()
    mappings_result.scalars.return_value.all.return_value = [existing_mapping]

    mock_db.execute.side_effect = [users_result, mappings_result]

    with patch.object(KekaClient, "get_all_employees", new_callable=AsyncMock, return_value={"data": keka_api_employees}):
        preview = await KekaEmployeeMappingService.get_mapping_preview(mock_db)

        assert preview["total_keka_employees"] == 5
        summary = preview["summary"]
        assert summary["mapped"] == 1
        assert summary["local_match"] == 2
        assert summary["unmapped"] == 1
        assert summary["conflict"] == 1

        items = preview["items"]
        # Item 1: mapped
        assert items[0]["status"] == "mapped"
        assert items[0]["matched_by"] == "existing_mapping"
        assert items[0]["matched_local_user_id"] == 1

        # Item 2: local_match by email
        assert items[1]["status"] == "local_match"
        assert items[1]["matched_by"] == "email"
        assert items[1]["matched_local_user_id"] == 2

        # Item 3: local_match by employee_number
        assert items[2]["status"] == "local_match"
        assert items[2]["matched_by"] == "employee_number"
        assert items[2]["matched_local_user_id"] == 3

        # Item 4: unmapped
        assert items[3]["status"] == "unmapped"
        assert items[3]["matched_by"] is None

        # Item 5: conflict
        assert items[4]["status"] == "conflict"
        assert "ambiguous" in items[4]["reason"].lower()


@pytest.mark.asyncio
async def test_mapping_preview_conflict_user_already_mapped():
    """Test conflict when matching local user is already mapped to a different Keka ID."""
    local_user = make_test_user(id=1, email="shared@company.com", employee_id="EMP001")
    existing_map = make_mock_mapping(keka_employee_id="keka-original", local_user_id=1, user=local_user)

    keka_api_employees = [
        {"id": "keka-second", "email": "shared@company.com", "employeeNumber": "EMP999", "displayName": "Impostor"},
    ]

    mock_db = AsyncMock()
    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [local_user]
    mappings_result = MagicMock()
    mappings_result.scalars.return_value.all.return_value = [existing_map]
    mock_db.execute.side_effect = [users_result, mappings_result]

    with patch.object(KekaClient, "get_all_employees", new_callable=AsyncMock, return_value={"data": keka_api_employees}):
        preview = await KekaEmployeeMappingService.get_mapping_preview(mock_db)
        assert preview["summary"]["conflict"] == 1
        assert preview["items"][0]["status"] == "conflict"
        assert "already mapped" in preview["items"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_mapping_preview_does_not_mutate_database():
    """Verify that get_mapping_preview strictly executes SELECTs and never writes to DB."""
    mock_db = AsyncMock()
    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = []
    mappings_result = MagicMock()
    mappings_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [users_result, mappings_result]

    with patch.object(KekaClient, "get_all_employees", new_callable=AsyncMock, return_value={"data": []}):
        await KekaEmployeeMappingService.get_mapping_preview(mock_db)

        # Ensure NO write/mutation methods were ever called
        assert not mock_db.add.called
        assert not mock_db.commit.called
        assert not mock_db.flush.called
        assert not mock_db.delete.called


# ---------------------------------------------------------------------------
# 4. HTTP Endpoints Tests
# ---------------------------------------------------------------------------

def test_endpoint_list_mappings_admin_success():
    mock_mapping = make_mock_mapping()

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "list_mappings", new_callable=AsyncMock, return_value=([mock_mapping], 1)):

        response = client.get("/api/v1/keka/mappings/employees", headers=admin_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["total"] == 1
        assert len(json_data["data"]["items"]) == 1
        assert json_data["data"]["items"][0]["keka_employee_id"] == "keka-uuid-1"


def test_endpoint_get_single_mapping_found():
    mock_mapping = make_mock_mapping()

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "get_by_keka_employee_id", new_callable=AsyncMock, return_value=mock_mapping):

        response = client.get("/api/v1/keka/mappings/employees/keka-uuid-1", headers=admin_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["keka_employee_id"] == "keka-uuid-1"


def test_endpoint_get_single_mapping_not_found():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "get_by_keka_employee_id", new_callable=AsyncMock, return_value=None):

        response = client.get("/api/v1/keka/mappings/employees/non-existent-uuid", headers=admin_headers())
        assert response.status_code == 404
        assert "no mapping found" in response.text.lower()


def test_endpoint_mapping_preview_admin_success():
    mock_preview = {
        "total_keka_employees": 1,
        "summary": {"mapped": 0, "local_match": 1, "unmapped": 0, "conflict": 0},
        "items": [{
            "keka_employee_id": "keka-1",
            "keka_name": "Test User",
            "keka_email": "test@company.com",
            "status": "local_match",
            "matched_local_user_id": 1,
            "matched_by": "email",
            "reason": "Found local match.",
        }],
    }

    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "get_mapping_preview", new_callable=AsyncMock, return_value=mock_preview):

        response = client.get("/api/v1/keka/employees/mapping-preview", headers=admin_headers())
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["total_keka_employees"] == 1
        assert json_data["data"]["summary"]["local_match"] == 1


def test_endpoints_forbidden_for_non_admin():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=EMPLOYEE_USER):
        # 1. list mappings
        r1 = client.get("/api/v1/keka/mappings/employees", headers=employee_headers())
        assert r1.status_code == 403

        # 2. single mapping
        r2 = client.get("/api/v1/keka/mappings/employees/some-id", headers=employee_headers())
        assert r2.status_code == 403

        # 3. preview
        r3 = client.get("/api/v1/keka/employees/mapping-preview", headers=employee_headers())
        assert r3.status_code == 403

        # 4. save mapping
        r4 = client.post("/api/v1/keka/mappings/employees", json={"keka_employee_id": "k1", "local_user_id": 1}, headers=employee_headers())
        assert r4.status_code == 403

        # 5. auto-sync
        r5 = client.post("/api/v1/keka/mappings/auto-sync", headers=employee_headers())
        assert r5.status_code == 403

        # 6. leave types
        r6 = client.get("/api/v1/keka/leave-types", headers=employee_headers())
        assert r6.status_code == 403


def test_endpoint_create_or_update_mapping():
    mock_mapping = make_mock_mapping(keka_employee_id="keka-uuid-new", local_user_id=1)
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "save_mapping", new_callable=AsyncMock, return_value=mock_mapping):

        response = client.post(
            "/api/v1/keka/mappings/employees",
            json={"keka_employee_id": "keka-uuid-new", "local_user_id": 1, "keka_employee_number": "EMP001"},
            headers=admin_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["keka_employee_id"] == "keka-uuid-new"


def test_endpoint_delete_mapping():
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "delete_mapping", new_callable=AsyncMock, return_value=True):

        response = client.delete(
            "/api/v1/keka/mappings/employees/keka-uuid-to-delete",
            headers=admin_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] is True


def test_endpoint_auto_sync():
    mock_auto_sync_res = {
        "mapped_count": 2,
        "skipped_count": 1,
        "total_evaluated": 3,
        "mapped_items": [],
    }
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "auto_sync_matched", new_callable=AsyncMock, return_value=mock_auto_sync_res):

        response = client.post(
            "/api/v1/keka/mappings/auto-sync",
            headers=admin_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["mapped_count"] == 2


def test_endpoint_get_keka_leave_types():
    mock_leave_types = [
        {"id": "lt-1", "name": "Casual Leave", "code": "CL", "description": "Casual"},
        {"id": "lt-2", "name": "Sick Leave", "code": "SL", "description": "Sick"},
    ]
    with patch("app.dependencies.auth.AuthRepository.get_user_by_id", return_value=ADMIN_USER), \
         patch.object(KekaEmployeeMappingService, "get_keka_leave_types", new_callable=AsyncMock, return_value=mock_leave_types):

        response = client.get(
            "/api/v1/keka/leave-types",
            headers=admin_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "Casual Leave"

