from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.modules.clients.model import Client
    from app.modules.users.model import User
    from app.modules.project_assignments.model import ProjectAssignment
    from app.modules.tool_allocations.model import ToolAllocation
    from app.modules.milestones.model import Milestone

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
    status: Mapped[str] = mapped_column(String(50), default="Milestone Planning", nullable=False)
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
    milestones: Mapped[List["Milestone"]] = relationship(
        "Milestone", back_populates="project", cascade="all, delete-orphan"
    )
    documents: Mapped[List["ProjectDocument"]] = relationship(
        "ProjectDocument", back_populates="project", cascade="all, delete-orphan"
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
                "monthly_cost": getattr(ta, "monthly_cost", 0.0) if getattr(ta, "monthly_cost", None) is not None else (getattr(ta, "tool", None).cost_per_month if getattr(ta, "tool", None) else 0.0),
                "seats": getattr(ta, "seats", 1),
                "allocation_date": str(ta.allocation_date) if getattr(ta, "allocation_date", None) else None,
                "deallocation_date": str(ta.deallocation_date) if getattr(ta, "deallocation_date", None) else None,
                "status": getattr(ta, "status", "Active")
            } 
            for ta in self.tool_allocations if ta.status.lower() == "active"
        ]



class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
