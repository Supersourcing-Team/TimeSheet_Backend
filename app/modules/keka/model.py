from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.users.model import User

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KekaEmployeeMapping(Base):
    """
    Mapping table connecting Keka HR employee UUIDs to local Timesheet users.
    Enforces 1:1 mapping between a Keka employee and a local user.
    """
    __tablename__ = "keka_employee_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    keka_employee_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    local_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    keka_employee_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="keka_mapping")
