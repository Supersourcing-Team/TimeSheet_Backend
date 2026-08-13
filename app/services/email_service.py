import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """
    Sends an email using configured SMTP settings or logs it if SMTP is not configured.
    """
    smtp_host = getattr(settings, "SMTP_HOST", None)
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USER", None)
    smtp_password = getattr(settings, "SMTP_PASSWORD", None)

    if not smtp_host or not smtp_user or not smtp_password:
        logger.info(
            f"[EMAIL MOCK] To: {to_email} | Subject: {subject} | Body: {body_text}"
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], msg.as_string())

        logger.info(f"Successfully sent email to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_timesheet_reminder_email(
    to_email: str,
    user_name: str,
    logged_hours: float,
    missing_hours: float,
) -> bool:
    """
    Sends a weekly timesheet reminder email to an employee with unfulfilled target hours.
    """
    subject = "Action Required: Weekly Timesheet Target Reminder"
    body_text = (
        f"Hi {user_name},\n\n"
        f"This is a friendly reminder to complete your timesheet entries for last week.\n"
        f"Hours Logged: {logged_hours:.1f} hrs\n"
        f"Target Required: 40.0 hrs (Missing: {missing_hours:.1f} hrs)\n\n"
        f"Please log in to the portal and complete your time entries as soon as possible.\n\n"
        f"Best regards,\nTimesheet Management System"
    )
    body_html = (
        f"<html><body>"
        f"<h3>Hi {user_name},</h3>"
        f"<p>This is a friendly reminder to complete your timesheet entries for last week.</p>"
        f"<ul>"
        f"<li><b>Hours Logged:</b> {logged_hours:.1f} hrs</li>"
        f"<li><b>Target Required:</b> 40.0 hrs</li>"
        f"<li><b>Missing:</b> <span style='color: red;'>{missing_hours:.1f} hrs</span></li>"
        f"</ul>"
        f"<p>Please log in to the portal and complete your time entries as soon as possible.</p>"
        f"<br/><p>Best regards,<br/><b>Timesheet Management System</b></p>"
        f"</body></html>"
    )
    return await send_email(to_email, subject, body_text, body_html)
