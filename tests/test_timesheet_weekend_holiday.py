import pytest
from datetime import date
from unittest.mock import AsyncMock, patch
from app.modules.timesheets.validator import TimesheetValidator
from app.core.exceptions import BadRequestException

def test_validate_not_weekend():
    # Saturday (2026-09-12) & Sunday (2026-09-13)
    saturday = date(2026, 9, 12)
    sunday = date(2026, 9, 13)
    monday = date(2026, 9, 14)

    with pytest.raises(BadRequestException) as exc_sat:
        TimesheetValidator.validate_not_weekend(saturday)
    assert "weekends" in exc_sat.value.detail.lower()

    with pytest.raises(BadRequestException) as exc_sun:
        TimesheetValidator.validate_not_weekend(sunday)
    assert "weekends" in exc_sun.value.detail.lower()

    # Weekday should pass without error
    TimesheetValidator.validate_not_weekend(monday)

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
