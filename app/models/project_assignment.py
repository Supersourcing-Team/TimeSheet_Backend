from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="assignments")
    user: Mapped["User"] = relationship("User", back_populates="project_assignments")
    timesheets: Mapped[List["Timesheet"]] = relationship(
        "Timesheet", back_populates="project_assignment"
    )
    weekend_work_requests: Mapped[List["WeekendWorkRequest"]] = relationship(
        "WeekendWorkRequest", back_populates="project_assignment"
    )
