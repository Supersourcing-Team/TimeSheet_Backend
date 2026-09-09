import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.modules.departments.model import Department
from app.modules.departments.schema import DepartmentCreate, DepartmentUpdate
from app.modules.departments.service import DepartmentService


class MockDepartment:
    def __init__(self, id=1, name="Design", code="DES", description="Design Team", is_active=True):
        self.id = id
        self.name = name
        self.code = code
        self.description = description
        self.is_active = is_active
        self.created_at = "2026-01-01T00:00:00Z"
        self.updated_at = "2026-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_create_department_success():
    mock_dept = MockDepartment(id=1, name="Design", code="DES", description="Design Team")
    data = DepartmentCreate(name="Design", code="DES", description="Design Team")

    service = DepartmentService(db=AsyncMock())
    with patch.object(service.repository, "get_by_name", AsyncMock(return_value=None)), \
         patch.object(service.repository, "get_by_code", AsyncMock(return_value=None)), \
         patch.object(service.repository, "create", AsyncMock(return_value=mock_dept)):
        
        result = await service.create_department(data)
        assert result.id == 1
        assert result.name == "Design"
        assert result.description == "Design Team"


@pytest.mark.asyncio
async def test_create_department_duplicate_name():
    mock_dept = MockDepartment(id=1, name="Design")
    data = DepartmentCreate(name="Design")

    service = DepartmentService(db=AsyncMock())
    with patch.object(service.repository, "get_by_name", AsyncMock(return_value=mock_dept)):
        with pytest.raises(Exception) as exc_info:
            await service.create_department(data)
        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_departments():
    mock_depts = [
        (MockDepartment(id=1, name="Engineering"), 5),
        (MockDepartment(id=2, name="Design"), 2),
    ]

    service = DepartmentService(db=AsyncMock())
    with patch.object(service.repository, "get_all_with_counts", AsyncMock(return_value=mock_depts)):
        results = await service.get_all_departments()
        assert len(results) == 2
        assert results[0].name == "Engineering"
        assert results[0].employee_count == 5
        assert results[1].name == "Design"
        assert results[1].employee_count == 2


@pytest.mark.asyncio
async def test_delete_department_success():
    mock_dept = MockDepartment(id=2, name="Design")

    service = DepartmentService(db=AsyncMock())
    with patch.object(service.repository, "get_by_id", AsyncMock(return_value=mock_dept)), \
         patch.object(service.repository, "count_assigned_users", AsyncMock(return_value=0)), \
         patch.object(service.repository, "delete", AsyncMock(return_value=None)):
        
        await service.delete_department(dept_id=2)


@pytest.mark.asyncio
async def test_delete_department_with_assigned_users_fails():
    mock_dept = MockDepartment(id=1, name="Engineering")

    service = DepartmentService(db=AsyncMock())
    with patch.object(service.repository, "get_by_id", AsyncMock(return_value=mock_dept)), \
         patch.object(service.repository, "count_assigned_users", AsyncMock(return_value=3)):
        
        with pytest.raises(Exception) as exc_info:
            await service.delete_department(dept_id=1)
        assert exc_info.value.status_code == 400
        assert "Cannot delete department" in exc_info.value.detail
