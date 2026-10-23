from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.milestones.model import Milestone
    from app.modules.project_assignments.model import ProjectAssignment
    from app.modules.users.model import User


class Timesheet(Base):
    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("project_assignments.id"), nullable=False
    )
    milestone_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True, index=True
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
    milestone: Mapped[Optional["Milestone"]] = relationship("Milestone")

    __table_args__ = (
        UniqueConstraint("user_id", "project_assignment_id", "timesheet_date", name="uq_user_project_date"),
    )

    @property
    def user_name(self) -> str:
        return f"{self.user.first_name} {self.user.last_name}" if self.user else "Unknown"

    @property
    def user_avatar(self) -> str:
        return getattr(self.user, "avatar_url", "") if self.user else ""

    @property
    def project_name(self) -> str:
        if self.project_assignment and getattr(self.project_assignment, "project", None):
            return self.project_assignment.project.project_name
        return "Unknown"

    @property
    def milestone_name(self) -> Optional[str]:
        return self.milestone.name if self.milestone else None

    @property
    def hours(self) -> float:
        return (self.billable_hours or 0.0) + (self.non_billable_hours or 0.0)

    @property
    def is_billable(self) -> bool:
        return (self.billable_hours or 0.0) > 0.0
