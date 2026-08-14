import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.weekly_timesheet_lock import lock_past_weekly_timesheets
from app.scheduler.weekly_timesheet_reminder import send_weekly_timesheet_reminders

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """
    Starts the AsyncIOScheduler and registers recurring background tasks.
    """
    if scheduler.running:
        logger.warning("Scheduler is already running.")
        return

    # Job 1: Weekly Timesheet Lock - Every Sunday at 23:59 (Midnight lock)
    scheduler.add_job(
        func=lock_past_weekly_timesheets,
        trigger=CronTrigger(day_of_week="sun", hour=23, minute=59),
        id="weekly_timesheet_lock_job",
        replace_existing=True,
        name="Lock past week timesheets",
    )

    # Job 2: Weekly Timesheet Reminder - Every Monday at 09:00 AM
    scheduler.add_job(
        func=send_weekly_timesheet_reminders,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_timesheet_reminder_job",
        replace_existing=True,
        name="Send weekly timesheet 40h reminders",
    )

    scheduler.start()
    logger.info("AsyncIOScheduler started successfully with scheduled cron jobs.")


def shutdown_scheduler():
    """
    Gracefully shuts down the scheduler.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("AsyncIOScheduler shut down successfully.")
