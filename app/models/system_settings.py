from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    org_name: Mapped[str] = mapped_column(String(255), default="SuperTime Enterprise")
    org_reg_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), default="admin@supertime.com")
    company_logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    time_zone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata (IST UTC+05:30)")
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    timesheet_approval_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    leave_request_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#2563eb")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
