from app.modules.leave_balances.model import LeaveBalance
from app.modules.roles.model import Role
from app.modules.departments.model import Department
from app.modules.milestones.assignment_model import MilestoneAssignment
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, func, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    joining_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ctc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    notifications_cleared_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users")
    leave_balances: Mapped[List["LeaveBalance"]] = relationship(
        "LeaveBalance", back_populates="user"
    )
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        "LeaveRequest", foreign_keys="[LeaveRequest.user_id]", back_populates="user"
    )
    managed_leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        "LeaveRequest",
        foreign_keys="[LeaveRequest.managers_user_id]",
        back_populates="manager",
    )
    managed_projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="project_manager"
    )
    project_assignments: Mapped[List["ProjectAssignment"]] = relationship(
        "ProjectAssignment", back_populates="user"
    )
    milestone_assignments: Mapped[List["MilestoneAssignment"]] = relationship(
        "MilestoneAssignment", back_populates="user"
    )
    timesheets: Mapped[List["Timesheet"]] = relationship("Timesheet", back_populates="user")

    @property
    def daily_cost(self) -> float:
        if self.ctc:
            return self.ctc / 260.0
        return 0.0
