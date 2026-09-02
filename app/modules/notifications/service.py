from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.leave_requests.model import LeaveRequest
from app.modules.users.model import User
from app.modules.weekend_work.model import WeekendWorkRequest
from app.modules.notifications.schema import NotificationItem, NotificationsResponse
from app.modules.project_assignments.model import ProjectAssignment
from app.modules.projects.model import Project


class NotificationService:
    """
    Derives real-time notifications for the current user from existing domain data.

    Notification logic per role:
    ─────────────────────────────────────────────────────────────────
    Employee  : own leave requests that were approved / rejected / cancelled
                own timesheet entries (submitted confirmation)
                own weekend work requests that were approved / rejected

    Admin/PM  : all pending leave requests awaiting review
                all pending weekend work requests awaiting review
                (employees' submitted timesheets that need PM attention)
    ─────────────────────────────────────────────────────────────────
    Notifications are sorted newest-first and capped at 30 items.
    """

    MAX_ITEMS = 30

    @staticmethod
    async def get_notifications(
        db: AsyncSession, current_user: User
    ) -> NotificationsResponse:
        notifications: List[NotificationItem] = []
        role_name: str = getattr(current_user.role, "name", "") or ""
        is_privileged = role_name in ("Admin", "Project_Manager", "Account_Manager")

        # ------------------------------------------------------------------
        # 1. Employee-facing: own leave requests with non-Pending status
        # ------------------------------------------------------------------
        leave_result = await db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.leave_type),
                selectinload(LeaveRequest.manager),
            )
            .filter(LeaveRequest.user_id == current_user.id)
            .order_by(LeaveRequest.updated_at.desc())
            .limit(20)
        )
        own_leaves: List[LeaveRequest] = list(leave_result.scalars().all())

        for lr in own_leaves:
            lt_name = lr.leave_type.name if lr.leave_type else "Leave"
            days = (lr.end_date - lr.start_date).days + 1

            if lr.status == "Approved":
                notifications.append(
                    NotificationItem(
                        id=f"leave_approved_{lr.id}",
                        type="leave_approved",
                        title="Leave Request Approved ✓",
                        description=(
                            f"Your {lt_name} request ({days} day(s), "
                            f"{lr.start_date} → {lr.end_date}) has been approved."
                        ),
                        timestamp=lr.updated_at,
                        is_read=False,
                        related_id=lr.id,
                        related_entity="leave_request",
                    )
                )
            elif lr.status == "Rejected":
                reason = f" Reason: {lr.rejection_reason}" if lr.rejection_reason else ""
                notifications.append(
                    NotificationItem(
                        id=f"leave_rejected_{lr.id}",
                        type="leave_rejected",
                        title="Leave Request Declined",
                        description=(
                            f"Your {lt_name} request ({days} day(s), "
                            f"{lr.start_date} → {lr.end_date}) was not approved.{reason}"
                        ),
                        timestamp=lr.updated_at,
                        is_read=False,
                        related_id=lr.id,
                        related_entity="leave_request",
                    )
                )
            elif lr.status == "Pending":
                notifications.append(
                    NotificationItem(
                        id=f"leave_pending_{lr.id}",
                        type="leave_requested",
                        title="Leave Request Submitted",
                        description=(
                            f"Your {lt_name} request for {days} day(s) "
                            f"({lr.start_date} → {lr.end_date}) is awaiting approval."
                        ),
                        timestamp=lr.created_at,
                        is_read=True,   # "informational" — not urgent for the employee
                        related_id=lr.id,
                        related_entity="leave_request",
                    )
                )

        # ------------------------------------------------------------------
        # 2. Employee-facing: own weekend work request status changes
        # ------------------------------------------------------------------
        ww_result = await db.execute(
            select(WeekendWorkRequest)
            .join(
                ProjectAssignment,
                WeekendWorkRequest.project_assignment_id == ProjectAssignment.id,
            )
            .options(
                selectinload(WeekendWorkRequest.project_assignment).selectinload(
                    ProjectAssignment.project
                ),
                selectinload(WeekendWorkRequest.approver),
            )
            .filter(ProjectAssignment.user_id == current_user.id)
            .order_by(WeekendWorkRequest.created_at.desc())
            .limit(10)
        )
        own_ww: List[WeekendWorkRequest] = list(ww_result.scalars().all())

        for ww in own_ww:
            proj_name = ww.project_name
            if ww.status == "Approved":
                notifications.append(
                    NotificationItem(
                        id=f"ww_approved_{ww.id}",
                        type="weekend_work_approved",
                        title="Weekend Work Approved ✓",
                        description=(
                            f"Your weekend work request for {proj_name} "
                            f"on {ww.work_date} ({ww.planned_hours}h) has been approved."
                        ),
                        timestamp=ww.approved_at or ww.created_at,
                        is_read=False,
                        related_id=ww.id,
                        related_entity="weekend_work",
                    )
                )
            elif ww.status == "Rejected":
                notifications.append(
                    NotificationItem(
                        id=f"ww_rejected_{ww.id}",
                        type="weekend_work_rejected",
                        title="Weekend Work Declined",
                        description=(
                            f"Your weekend work request for {proj_name} "
                            f"on {ww.work_date} was not approved."
                        ),
                        timestamp=ww.approved_at or ww.created_at,
                        is_read=False,
                        related_id=ww.id,
                        related_entity="weekend_work",
                    )
                )

        # ------------------------------------------------------------------
        # 3. Privileged roles: pending leave requests needing review
        # ------------------------------------------------------------------
        if is_privileged:
            pending_leaves_result = await db.execute(
                select(LeaveRequest)
                .options(
                    selectinload(LeaveRequest.user),
                    selectinload(LeaveRequest.leave_type),
                )
                .filter(LeaveRequest.status == "Pending")
                .order_by(LeaveRequest.created_at.desc())
                .limit(15)
            )
            pending_leaves: List[LeaveRequest] = list(
                pending_leaves_result.scalars().all()
            )

            for lr in pending_leaves:
                requester_name = (
                    f"{lr.user.first_name} {lr.user.last_name}" if lr.user else "An employee"
                )
                lt_name = lr.leave_type.name if lr.leave_type else "Leave"
                days = (lr.end_date - lr.start_date).days + 1
                notifications.append(
                    NotificationItem(
                        id=f"pending_leave_{lr.id}",
                        type="leave_requested",
                        title="Leave Request Awaiting Approval",
                        description=(
                            f"{requester_name} applied for {lt_name} — "
                            f"{days} day(s) ({lr.start_date} → {lr.end_date})."
                        ),
                        timestamp=lr.created_at,
                        is_read=False,
                        related_id=lr.id,
                        related_entity="leave_request",
                    )
                )

        # ------------------------------------------------------------------
        # 4. Privileged roles: pending weekend work requests needing review
        # ------------------------------------------------------------------
        if is_privileged:
            pending_ww_result = await db.execute(
                select(WeekendWorkRequest)
                .join(
                    ProjectAssignment,
                    WeekendWorkRequest.project_assignment_id == ProjectAssignment.id,
                )
                .join(Project, ProjectAssignment.project_id == Project.id)
                .options(
                    selectinload(WeekendWorkRequest.project_assignment)
                    .selectinload(ProjectAssignment.user),
                    selectinload(WeekendWorkRequest.project_assignment)
                    .selectinload(ProjectAssignment.project),
                )
                .filter(WeekendWorkRequest.status == "Pending")
                .order_by(WeekendWorkRequest.created_at.desc())
                .limit(10)
            )
            pending_ww: List[WeekendWorkRequest] = list(
                pending_ww_result.scalars().all()
            )

            for ww in pending_ww:
                user_name = ww.user_name
                proj_name = ww.project_name
                notifications.append(
                    NotificationItem(
                        id=f"pending_ww_{ww.id}",
                        type="weekend_work_requested",
                        title="Weekend Work Request Pending",
                        description=(
                            f"{user_name} requested weekend work on {ww.work_date} "
                            f"for {proj_name} ({ww.planned_hours}h)."
                        ),
                        timestamp=ww.created_at,
                        is_read=False,
                        related_id=ww.id,
                        related_entity="weekend_work",
                    )
                )

        # ------------------------------------------------------------------
        # 5. Sort by timestamp descending, cap, compute unread count
        # ------------------------------------------------------------------
        if current_user.notifications_cleared_at:
            # ensure current_user.notifications_cleared_at is offset-aware
            cleared_at = current_user.notifications_cleared_at
            if cleared_at.tzinfo is None:
                from datetime import timezone
                cleared_at = cleared_at.replace(tzinfo=timezone.utc)
            
            filtered_notifications = []
            for n in notifications:
                n_time = n.timestamp
                if n_time.tzinfo is None:
                    from datetime import timezone
                    n_time = n_time.replace(tzinfo=timezone.utc)
                if n_time > cleared_at:
                    filtered_notifications.append(n)
            notifications = filtered_notifications

        notifications.sort(key=lambda n: n.timestamp, reverse=True)
        notifications = notifications[: NotificationService.MAX_ITEMS]
        unread_count = sum(1 for n in notifications if not n.is_read)

        return NotificationsResponse(
            notifications=notifications,
            unread_count=unread_count,
        )

    @staticmethod
    async def clear_all_notifications(db: AsyncSession, current_user: User) -> None:
        from datetime import datetime, timezone
        current_user.notifications_cleared_at = datetime.now(timezone.utc)
        db.add(current_user)
        await db.commit()
