import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from app.modules.timesheets.validator import TimesheetValidator
from app.core.exceptions import BadRequestException

@pytest.mark.asyncio
async def test_validate_not_weekend():
    # Saturday (2026-09-12) & Sunday (2026-09-13)
    saturday = date(2026, 9, 12)
    sunday = date(2026, 9, 13)
    monday = date(2026, 9, 14)

    # 1. Saturday without approved request raises BadRequestException
    mock_db = AsyncMock()
    mock_res_empty = MagicMock()
    mock_res_empty.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_res_empty

    with pytest.raises(BadRequestException) as exc_sat:
        await TimesheetValidator.validate_not_weekend(
            db=mock_db, user_id=1, project_assignment_id=10, timesheet_date=saturday
        )
    assert "weekends" in exc_sat.value.detail.lower()

    # 2. Sunday without approved request raises BadRequestException
    with pytest.raises(BadRequestException) as exc_sun:
        await TimesheetValidator.validate_not_weekend(
            db=mock_db, user_id=1, project_assignment_id=10, timesheet_date=sunday
        )
    assert "weekends" in exc_sun.value.detail.lower()

    # 3. Saturday with approved request passes
    class MockApprovedRequest:
        id = 99
        status = "Approved"

    mock_res_approved = MagicMock()
    mock_res_approved.scalars.return_value.first.return_value = MockApprovedRequest()
    mock_db.execute.return_value = mock_res_approved

    await TimesheetValidator.validate_not_weekend(
        db=mock_db, user_id=1, project_assignment_id=10, timesheet_date=saturday
    )

    # 4. Weekday should pass without querying db
    mock_db_unused = AsyncMock()
    await TimesheetValidator.validate_not_weekend(
        db=mock_db_unused, user_id=1, project_assignment_id=10, timesheet_date=monday
    )
    mock_db_unused.execute.assert_not_called()

@pytest.mark.asyncio
async def test_validate_not_holiday():
    class MockHoliday:
        name = "Independence Day"

    test_holiday_date = date(2026, 8, 15)
    normal_date = date(2026, 8, 14)

    with patch("app.modules.holidays.repository.HolidayRepository.get_by_date", AsyncMock(return_value=MockHoliday())):
        with pytest.raises(BadRequestException) as exc:
            await TimesheetValidator.validate_not_holiday(db=AsyncMock(), timesheet_date=test_holiday_date)
        assert "Independence Day" in exc.value.detail

    with patch("app.modules.holidays.repository.HolidayRepository.get_by_date", AsyncMock(return_value=None)):
        await TimesheetValidator.validate_not_holiday(db=AsyncMock(), timesheet_date=normal_date)
