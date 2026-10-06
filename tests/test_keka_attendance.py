from unittest.mock import AsyncMock, patch
import pytest

from app.modules.keka.attendance_service import KekaAttendanceService
from app.services.keka.keka_client import KekaClient


def admin_headers():
    return {"Authorization": "Bearer fake-admin-token"}


@pytest.mark.asyncio
async def test_keka_client_attendance_methods():
    mock_response = {
        "data": [
            {
                "employeeId": "keka-uuid-1",
                "attendanceDate": "2026-09-28T00:00:00",
                "dayStatus": "Present",
                "firstIn": "2026-09-28T09:15:00",
                "lastOut": "2026-09-28T18:00:00",
                "totalWorkingHours": 8.75,
                "effectiveWorkingHours": 8.0,
            }
        ],
        "totalPages": 1,
        "totalRecords": 1,
    }

    with patch.object(KekaClient, "request", new_callable=AsyncMock, return_value=mock_response):
        single_page = await KekaClient.get_attendance(from_date="2026-09-01", to_date="2026-09-05")
        assert len(single_page["data"]) == 1

        all_records = await KekaClient.get_all_attendance(from_date="2026-09-01", to_date="2026-09-05")
        assert len(all_records) == 1
        assert all_records[0]["employeeId"] == "keka-uuid-1"


@pytest.mark.asyncio
async def test_attendance_service_normalization():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    class MockUser:
        first_name = "Jane"
        last_name = "Doe"
        email = "jane@example.com"

    class MockMapping:
        keka_employee_id = "keka-uuid-1"
        keka_employee_number = "EMP001"
        local_user_id = 42
        user = MockUser()

    class MockScalarResult:
        def scalars(self):
            class MockScalars:
                def all(self):
                    return [MockMapping()]
            return MockScalars()

    mock_db.execute.return_value = MockScalarResult()

    keka_api_attendance = [
        {
            "employeeId": "keka-uuid-1",
            "attendanceDate": "2026-09-28T00:00:00",
            "dayStatus": "Present",
            "firstIn": "2026-09-28T09:00:00",
            "lastOut": "2026-09-28T18:00:00",
            "effectiveWorkingHours": 8.0,
        },
        {
            "employeeId": "keka-uuid-unmapped",
            "attendanceDate": "2026-09-28T00:00:00",
            "dayStatus": 1,
            "firstIn": "2026-09-28T10:00:00",
            "lastOut": None,  # Missing punch
            "effectiveWorkingHours": 4.0,
        },
    ]

    with patch.object(KekaClient, "get_all_attendance", new_callable=AsyncMock, return_value=keka_api_attendance):
        records = await KekaAttendanceService.get_attendance_records(
            db=mock_db,
            from_date="2026-09-28",
            to_date="2026-09-28",
        )

        assert len(records) == 2
        # First record is mapped
        assert records[0]["is_mapped"] is True
        assert records[0]["local_user_id"] == 42
        assert records[0]["local_user_name"] == "Jane Doe"
        assert records[0]["first_in"] == "09:00"
        assert records[0]["last_out"] == "18:00"
        assert records[0]["is_missing_punch"] is False

        # Second record is unmapped and has missing punch
        assert records[1]["is_mapped"] is False
        assert records[1]["local_user_id"] is None
        assert records[1]["is_missing_punch"] is True
