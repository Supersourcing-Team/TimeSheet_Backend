import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from app.modules.dashboard.service import DashboardService
from app.modules.timesheets.model import Timesheet
from app.modules.users.model import User

@pytest.mark.asyncio
async def test_dashboard_summary_with_timesheet_entries():
    """Verify that DashboardService.get_summary calculates billable, non-billable, and total hours correctly."""
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.role = MagicMock()
    mock_user.role.name = "Employee"

    entry1 = MagicMock(spec=Timesheet)
    entry1.billable_hours = 6.5
    entry1.non_billable_hours = 1.5

    entry2 = MagicMock(spec=Timesheet)
    entry2.billable_hours = 8.0
    entry2.non_billable_hours = 0.0

    timesheet_entries = [entry1, entry2]

    with patch("app.modules.timesheets.repository.TimesheetRepository.get_entries_in_range", new_callable=AsyncMock) as mock_get_entries, \
         patch("app.modules.project_assignments.repository.ProjectAssignmentRepository.get_by_user", new_callable=AsyncMock) as mock_assignments, \
         patch("app.modules.leave_balances.repository.LeaveBalanceRepository.get_by_user_and_year", new_callable=AsyncMock) as mock_leaves, \
         patch("app.modules.leave_requests.repository.LeaveRequestRepository.list_by_user", new_callable=AsyncMock) as mock_leave_reqs:

        mock_get_entries.return_value = timesheet_entries
        mock_assignments.return_value = []
        mock_leaves.return_value = []
        mock_leave_reqs.return_value = ([], 0)

        # Mock db.execute for holiday query
        holiday_mock = MagicMock()
        holiday_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = holiday_mock

        summary = await DashboardService.get_summary(mock_db, mock_user)

        assert summary.timesheet_summary.billable_hours == 14.5
        assert summary.timesheet_summary.non_billable_hours == 1.5
        assert summary.timesheet_summary.total_logged_hours == 16.0
        assert summary.timesheet_summary.target_weekly_hours == 40.0
