import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date

from app.scheduler.weekly_timesheet_lock import lock_past_weekly_timesheets
from app.scheduler.weekly_timesheet_reminder import send_weekly_timesheet_reminders, get_user_logged_hours_for_range
from app.services.email_service import (
    send_email,
    send_leave_approved_email,
    send_leave_rejected_email,
    send_timesheet_reminder_email,
    send_welcome_email,
)


class MockUser:
    def __init__(self, id=1, first_name="John", last_name="Doe", email="john@test.com", status="Active"):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.status = status


@pytest.mark.asyncio
async def test_send_email_mock_success():
    result = await send_email(
        to_email="test@example.com",
        subject="Test Subject",
        body_text="Test Body",
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_timesheet_reminder_email():
    result = await send_timesheet_reminder_email(
        to_email="employee@test.com",
        user_name="John Doe",
        logged_hours=32.0,
        missing_hours=8.0,
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_leave_approved_email():
    result = await send_leave_approved_email(
        to_email="employee@test.com",
        user_name="John Doe",
        leave_type="Paid Leave",
        start_date="2026-08-20",
        end_date="2026-08-22",
        working_days=3,
        approver_name="Admin Manager",
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_leave_rejected_email():
    result = await send_leave_rejected_email(
        to_email="employee@test.com",
        user_name="John Doe",
        leave_type="Paid Leave",
        start_date="2026-08-20",
        end_date="2026-08-22",
        rejection_reason="Project delivery deadline conflicts",
        reviewer_name="Admin Manager",
    )
    assert result is True


@pytest.mark.asyncio
async def test_send_welcome_email():
    result = await send_welcome_email(
        to_email="new_employee@test.com",
        user_name="Jane Doe",
        role_name="Software Engineer",
        employee_id="EMP-102",
    )
    assert result is True



@pytest.mark.asyncio
async def test_lock_past_weekly_timesheets():
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 5
    mock_session.execute.return_value = mock_res

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session

    with patch("app.scheduler.weekly_timesheet_lock.AsyncSessionLocal", return_value=mock_cm):
        count = await lock_past_weekly_timesheets()
        assert count == 5


@pytest.mark.asyncio
async def test_send_weekly_timesheet_reminders():
    user = MockUser(id=1, email="test@test.com")
    
    with patch("app.scheduler.weekly_timesheet_reminder.get_user_logged_hours_for_range", new_callable=AsyncMock, return_value=30.0), \
         patch("app.scheduler.weekly_timesheet_reminder.send_timesheet_reminder_email", new_callable=AsyncMock, return_value=True) as mock_send:

        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [user]
        mock_session.execute.return_value = mock_res

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session

        with patch("app.scheduler.weekly_timesheet_reminder.AsyncSessionLocal", return_value=mock_cm):
            count = await send_weekly_timesheet_reminders()
            assert count == 1
            mock_send.assert_called_once()

