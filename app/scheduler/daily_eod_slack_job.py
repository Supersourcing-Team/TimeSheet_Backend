import logging
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from app.core.database import AsyncSessionLocal
from app.services.eod_report_service import EodReportService

logger = logging.getLogger(__name__)


async def dispatch_daily_eod_report() -> dict:
    """
    Automated background job scheduled daily at 8:00 PM IST.
    Checks if employees submitted timesheets for today:
    - If yes: Generates the EOD Excel report and sends it to Slack.
    - If no (e.g. weekend/holiday with no work): Skips dispatch cleanly.
    """
    try:
        ist_tz = ZoneInfo("Asia/Kolkata")
        today = datetime.now(ist_tz).date()
    except Exception:
        # Fallback to local system date if timezone resolution fails
        today = datetime.now().date()

    logger.info(f"[Daily EOD Scheduler] Starting scheduled EOD Slack dispatch check for date: {today}")

    async with AsyncSessionLocal() as db:
        try:
            # 1. Check if there are any submissions for today
            entries = await EodReportService.get_daily_eod_entries(db, today)
            if not entries:
                logger.info(
                    f"[Daily EOD Scheduler] No timesheets found for {today}. Skipping Slack EOD report dispatch."
                )
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "No submissions found for date",
                    "date": str(today),
                }

            logger.info(
                f"[Daily EOD Scheduler] Found {len(entries)} timesheet submission(s) for {today}. Dispatching Excel report to Slack..."
            )

            # 2. Dispatch report to Slack
            result = await EodReportService.send_daily_eod_to_slack(db, today)
            logger.info(f"[Daily EOD Scheduler] Slack dispatch completed with result: {result}")
            return result

        except Exception as e:
            logger.error(f"[Daily EOD Scheduler] Error during scheduled EOD Slack dispatch: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}
