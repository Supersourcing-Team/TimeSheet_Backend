import logging
from datetime import date, timedelta
from typing import List, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.timesheet import Timesheet
from app.models.user import User
from app.services.email_service import send_timesheet_reminder_email

logger = logging.getLogger(__name__)


async def get_user_logged_hours_for_range(
    user_id: int, start_date: date, end_date: date
) -> float:
    """Calculates total hours logged by a user between start_date and end_date."""
    async with AsyncSessionLocal() as db:
        query = select(
            func.coalesce(func.sum(Timesheet.billable_hours + Timesheet.non_billable_hours), 0.0)
        ).filter(
            Timesheet.user_id == user_id,
            Timesheet.timesheet_date >= start_date,
            Timesheet.timesheet_date <= end_date,
        )
        res = await db.execute(query)
        return float(res.scalar_one())


async def send_weekly_timesheet_reminders() -> int:
    """
    Background job scheduled every Monday morning at 09:00 AM.
    Checks employees with fewer than 40 hours logged for preceding week (Monday to Friday) and sends email reminders.
    Returns the number of reminder emails sent.
    """
    logger.info("Executing weekly timesheet reminder email job...")
    today = date.today()
    # Current week's Monday
    current_monday = today - timedelta(days=today.weekday())
    # Preceding week Monday & Friday
    last_monday = current_monday - timedelta(days=7)
    last_friday = current_monday - timedelta(days=3)

    reminders_sent = 0

    async with AsyncSessionLocal() as db:
        try:
            # Query all active employees
            query = select(User).filter(User.status == "Active")
            res = await db.execute(query)
            users = list(res.scalars().all())

            for user in users:
                logged_hours = await get_user_logged_hours_for_range(
                    user.id, last_monday, last_friday
                )
                target_hours = 40.0

                if logged_hours < target_hours:
                    missing = target_hours - logged_hours
                    user_full_name = f"{user.first_name} {user.last_name}".strip()
                    success = await send_timesheet_reminder_email(
                        to_email=user.email,
                        user_name=user_full_name,
                        logged_hours=logged_hours,
                        missing_hours=missing,
                        period_start=last_monday.strftime("%d %b %Y"),
                        period_end=last_friday.strftime("%d %b %Y"),
                    )
                    if success:
                        reminders_sent += 1

            logger.info(
                f"Weekly timesheet reminder job completed. Sent {reminders_sent} reminder email(s) for period {last_monday} to {last_friday}."
            )
            return reminders_sent
        except Exception as e:
            logger.error(f"Error executing weekly timesheet reminder job: {e}")
            return 0
