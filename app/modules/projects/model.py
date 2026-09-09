from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.modules.clients.model import Client
    from app.modules.users.model import User
    from app.modules.project_assignments.model import ProjectAssignment
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
        all_tools = []
        for m in self.milestones:
            for ta in getattr(m, "tool_allocations", []):
                if getattr(ta, "status", "Active").lower() == "active":
                    tool = getattr(ta, "tool", None)
                    monthly_cost = getattr(ta, "monthly_cost", None)
                    if monthly_cost is None:
                        monthly_cost = getattr(tool, "cost_per_month", 0.0) if tool else 0.0
                    
                    all_tools.append({
                        "id": ta.tool_id,
                        "toolId": ta.tool_id,
                        "allocationId": ta.id,
                        "milestoneId": m.id,
                        "milestoneName": m.name,
                        "name": tool.name if tool else "Unknown",
                        "category": tool.category if tool else "Unknown",
                        "monthlyCost": monthly_cost,
                        "seats": getattr(ta, "seats", 1),
                        "allocationDate": str(ta.allocation_date) if getattr(ta, "allocation_date", None) else None,
                        "deallocationDate": str(ta.deallocation_date) if getattr(ta, "deallocation_date", None) else None,
                        "status": getattr(ta, "status", "Active")
                    })
        return all_tools



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
