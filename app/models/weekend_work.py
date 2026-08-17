from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WeekendWorkRequest(Base):
    __tablename__ = "weekend_work_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("project_assignments.id"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project_assignment: Mapped["ProjectAssignment"] = relationship(
        "ProjectAssignment", back_populates="weekend_work_requests"
    )
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])

    @property
    def user_name(self) -> str:
        if self.project_assignment and getattr(self.project_assignment, "user", None):
            return f"{self.project_assignment.user.first_name} {self.project_assignment.user.last_name}"
        return "Unknown"

    @property
    def user_avatar(self) -> str:
        if self.project_assignment and getattr(self.project_assignment, "user", None):
            return getattr(self.project_assignment.user, "avatar_url", "")
        return ""

    @property
    def project_name(self) -> str:
        if self.project_assignment and getattr(self.project_assignment, "project", None):
            return self.project_assignment.project.project_name
        return "Unknown"
