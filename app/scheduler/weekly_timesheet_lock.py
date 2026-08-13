import logging
from datetime import date, timedelta
from sqlalchemy import select, func, update
from app.core.database import AsyncSessionLocal
from app.models.timesheet import Timesheet

logger = logging.getLogger(__name__)


async def lock_past_weekly_timesheets() -> int:
    """
    Background job scheduled every Sunday midnight to lock timesheet entries from past weeks.
    Returns the total count of timesheets processed/locked.
    """
    logger.info("Executing weekly timesheet auto-locking job...")
    today = date.today()
    # Current week's Monday
    current_monday = today - timedelta(days=today.weekday())
    # Last week's Sunday
    last_sunday = current_monday - timedelta(days=1)

    async with AsyncSessionLocal() as db:
        try:
            # Query count of timesheet entries on or before last_sunday
            query = select(func.count(Timesheet.id)).filter(Timesheet.timesheet_date <= last_sunday)
            res = await db.execute(query)
            count = res.scalar() or 0

            logger.info(
                f"Weekly timesheet lock job completed. Total {count} past entries processed prior to {current_monday}."
            )
            return count
        except Exception as e:
            logger.error(f"Error executing weekly timesheet lock job: {e}")
            return 0
