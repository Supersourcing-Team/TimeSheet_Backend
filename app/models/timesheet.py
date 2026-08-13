from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from sqlalchemy import UniqueConstraint


class Timesheet(Base):
    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("project_assignments.id"), nullable=False
    )
    timesheet_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    billable_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    billable_work_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    non_billable_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    non_billable_work_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Workflow status: draft → pending → approved / rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted", server_default="submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="timesheets")
    project_assignment: Mapped["ProjectAssignment"] = relationship(
        "ProjectAssignment", back_populates="timesheets"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "project_assignment_id", "timesheet_date", name="uq_user_project_date"),
    )
