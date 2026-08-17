from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    project_manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Planning", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship("Client", back_populates="projects")
    project_manager: Mapped["User"] = relationship("User", back_populates="managed_projects")
    assignments: Mapped[List["ProjectAssignment"]] = relationship(
        "ProjectAssignment", back_populates="project"
    )
    tool_allocations: Mapped[List["ToolAllocation"]] = relationship(
        "ToolAllocation", back_populates="project"
    )

    @property
    def client_name(self) -> str:
        return self.client.name if self.client else "Unknown"

    @property
    def project_manager_name(self) -> str:
        if self.project_manager:
            return f"{self.project_manager.first_name} {self.project_manager.last_name}"
        return "Unknown"

    @property
    def assigned_user_ids(self) -> List[int]:
        return [a.user_id for a in self.assignments if a.is_active]

    @property
    def tools(self) -> List[dict]:
        return [
            {
                "id": ta.tool_id,
                "allocation_id": ta.id,
                "name": getattr(ta, "tool", None).name if getattr(ta, "tool", None) else "Unknown",
                "category": getattr(ta, "tool", None).category if getattr(ta, "tool", None) else "Unknown",
                "monthly_cost": getattr(ta, "tool", None).cost_per_month if getattr(ta, "tool", None) else 0.0,
                "allocated_hours": 0
            } 
            for ta in self.tool_allocations if ta.status.lower() == "active"
        ]
