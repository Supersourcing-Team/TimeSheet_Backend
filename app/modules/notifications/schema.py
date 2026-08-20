from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel


NotificationType = Literal[
    "timesheet_submitted",
    "timesheet_approved",
    "timesheet_rejected",
    "leave_requested",
    "leave_approved",
    "leave_rejected",
    "leave_cancelled",
    "weekend_work_requested",
    "weekend_work_approved",
    "weekend_work_rejected",
    "pending_approval",
]


class NotificationItem(BaseModel):
    id: str
    type: NotificationType
    title: str
    description: str
    timestamp: datetime
    is_read: bool = False
    # Optional metadata for deep-linking
    related_id: Optional[int] = None
    related_entity: Optional[str] = None  # "timesheet" | "leave_request" | "weekend_work"


class NotificationsResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int
