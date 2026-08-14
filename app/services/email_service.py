import logging
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Jinja2 Template Loader
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email_template(template_name: str, context: Dict[str, Any]) -> str:
    """Renders an HTML email template with given context variables."""
    try:
        template = jinja_env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        logger.error(f"Error rendering email template '{template_name}': {e}")
        return ""


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


async def send_leave_approved_email(
    to_email: str,
    user_name: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    working_days: int,
    approver_name: str,
) -> bool:
    """Dispatches a formatted Leave Approved notification email."""
    subject = f"Leave Request Approved: {leave_type}"
    body_text = (
        f"Hi {user_name},\n\n"
        f"Your leave request for {leave_type} ({start_date} to {end_date}, {working_days} day(s)) "
        f"has been approved by {approver_name}.\n\n"
        f"Best regards,\nTimesheet Management System"
    )
    context = {
        "user_name": user_name,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "working_days": working_days,
        "approver_name": approver_name,
    }
    body_html = render_email_template("leave_approved.html", context)
    return await send_email(to_email, subject, body_text, body_html)


async def send_leave_rejected_email(
    to_email: str,
    user_name: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    rejection_reason: Optional[str] = None,
    reviewer_name: str = "Administrator",
) -> bool:
    """Dispatches a formatted Leave Rejected notification email."""
    subject = f"Leave Request Update: {leave_type}"
    reason_str = f"\nReason: {rejection_reason}" if rejection_reason else ""
    body_text = (
        f"Hi {user_name},\n\n"
        f"Your leave request for {leave_type} ({start_date} to {end_date}) "
        f"was reviewed by {reviewer_name} and not approved.{reason_str}\n\n"
        f"Best regards,\nTimesheet Management System"
    )
    context = {
        "user_name": user_name,
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "rejection_reason": rejection_reason,
        "reviewer_name": reviewer_name,
    }
    body_html = render_email_template("leave_rejected.html", context)
    return await send_email(to_email, subject, body_text, body_html)


async def send_weekly_timesheet_reminder_email(
    to_email: str,
    user_name: str,
    logged_hours: float,
    missing_hours: float,
    period_start: str = "Monday",
    period_end: str = "Sunday",
) -> bool:
    """Dispatches a formatted Weekly Timesheet Target Reminder email."""
    subject = "Action Required: Weekly Timesheet Target Reminder"
    body_text = (
        f"Hi {user_name},\n\n"
        f"This is a friendly reminder to complete your timesheet entries for period ({period_start} to {period_end}).\n"
        f"Hours Logged: {logged_hours:.1f} hrs | Target: 40.0 hrs | Missing: {missing_hours:.1f} hrs\n\n"
        f"Best regards,\nTimesheet Management System"
    )
    context = {
        "user_name": user_name,
        "logged_hours": f"{logged_hours:.1f}",
        "missing_hours": f"{missing_hours:.1f}",
        "period_start": period_start,
        "period_end": period_end,
    }
    body_html = render_email_template("weekly_timesheet_reminder.html", context)
    return await send_email(to_email, subject, body_text, body_html)


async def send_welcome_email(
    to_email: str,
    user_name: str,
    role_name: str,
    employee_id: str,
) -> bool:
    """Dispatches a formatted Welcome email to a newly created employee."""
    subject = "Welcome to Timesheet Management System!"
    body_text = (
        f"Hi {user_name},\n\n"
        f"Welcome aboard! Your employee profile ({employee_id}) with role '{role_name}' "
        f"has been created and activated.\n\n"
        f"Best regards,\nTimesheet Management System"
    )
    context = {
        "user_name": user_name,
        "email": to_email,
        "role_name": role_name,
        "employee_id": employee_id,
    }
    body_html = render_email_template("welcome.html", context)
    return await send_email(to_email, subject, body_text, body_html)


# Alias for backward compatibility with scheduler
send_timesheet_reminder_email = send_weekly_timesheet_reminder_email

