from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.milestone import Milestone
    from app.models.user import User

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MilestoneAssignment(Base):
    __tablename__ = "milestone_assignments"
    __table_args__ = (UniqueConstraint("milestone_id", "user_id", name="uq_milestone_user_assignment"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    milestone: Mapped["Milestone"] = relationship("Milestone", back_populates="assignments")
    user: Mapped["User"] = relationship("User", back_populates="milestone_assignments")
