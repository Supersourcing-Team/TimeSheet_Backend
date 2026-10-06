import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.leave_requests.model import LeaveRequest
from app.services.keka.keka_auth import KekaAuthError
from app.services.keka.keka_client import KekaAPIError, KekaClient

logger = logging.getLogger(__name__)


class KekaMappingNotFoundError(Exception):
    """Raised when an operation requires an existing Keka employee mapping that was not found."""

    def __init__(self, user_id: int, message: Optional[str] = None):
        self.user_id = user_id
        super().__init__(
            message
            or f"No Keka employee mapping found for local user ID {user_id}. Please map the employee first."
        )


class KekaLeaveService:
    """Service handling local LeaveRequest synchronization to Keka."""

    @staticmethod
    async def get_keka_employee_id_for_user(db: AsyncSession, user_id: int) -> str:
        """
        Resolves local user_id -> keka_employee_id from keka_employee_mappings.
        Raises KekaMappingNotFoundError if unmapped. Does NOT create mapping automatically.
        """
        mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
        if not mapping or not mapping.keka_employee_id:
            raise KekaMappingNotFoundError(user_id=user_id)
        return mapping.keka_employee_id.strip()

    @staticmethod
    async def sync_leave_to_keka(
        db: AsyncSession,
        leave_request: LeaveRequest,
        keka_leave_type_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Pushes a local LeaveRequest to Keka via POST /time/leaverequests.
        - Resolves Keka employee UUID via mapping table.
        - Translates dates and sessions into Keka payload format.
        - Updates local LeaveRequest with sync metadata.
        - Does NOT alter the local leave request status.
        """
        # 1. Resolve Keka employee UUID
        try:
            keka_employee_id = await KekaLeaveService.get_keka_employee_id_for_user(
                db, leave_request.user_id
            )
        except KekaMappingNotFoundError as err:
            err_msg = str(err)
            logger.info("Cannot sync leave %s to Keka: %s", leave_request.id, err_msg)
            leave_request.synced_to_keka = False
            leave_request.last_sync_error = err_msg
            await db.commit()
            await db.refresh(leave_request)
            return {
                "success": False,
                "synced": False,
                "local_leave_id": leave_request.id,
                "keka_leave_request_id": None,
                "error": err_msg,
                "message": err_msg,
            }

        # 2. Determine Keka leave type ID
        resolved_keka_leave_type = keka_leave_type_id
        if not resolved_keka_leave_type:
            lt_rel = getattr(leave_request, "leave_type", None)
            if lt_rel and getattr(lt_rel, "keka_leave_type_id", None):
                resolved_keka_leave_type = lt_rel.keka_leave_type_id
            elif leave_request.leave_type_id:
                try:
                    from app.modules.leave_types.repository import LeaveTypeRepository
                    local_lt = await LeaveTypeRepository.get_by_id(db, leave_request.leave_type_id)
                    if local_lt and hasattr(local_lt, "keka_leave_type_id") and not hasattr(local_lt, "__await__"):
                        resolved_keka_leave_type = getattr(local_lt, "keka_leave_type_id", None)
                except Exception:
                    pass

        leave_type_to_use = (
            resolved_keka_leave_type
            or settings.KEKA_DEFAULT_LEAVE_TYPE_ID
            or str(leave_request.leave_type_id or "default")
        ).strip()

        # 3. Format dates (ISO 8601)
        from_date_str = f"{leave_request.start_date.isoformat()}T00:00:00Z"
        to_date_str = f"{leave_request.end_date.isoformat()}T00:00:00Z"

        # 4. Determine sessions (Keka SessionType enum: 0 = First Half / Session 1, 1 = Second Half / Session 2)
        from_session = 0
        to_session = 1
        if leave_request.leave_duration_type == "half_day":
            if leave_request.half_day_period == "first":
                from_session = 0
                to_session = 0
            elif leave_request.half_day_period == "second":
                from_session = 1
                to_session = 1

        reason_text = (leave_request.reason or "").strip() or "Applied via Timesheet Portal"

        # 5. Call Keka API
        try:
            keka_res = await KekaClient.create_leave_request(
                employee_id=keka_employee_id,
                from_date=from_date_str,
                to_date=to_date_str,
                leave_type_id=leave_type_to_use,
                reason=reason_text,
                requested_by=keka_employee_id,
                from_session=from_session,
                to_session=to_session,
                note=f"Local Leave ID: {leave_request.id}",
            )

            # Response structure: {"succeeded": True, "data": "keka-leave-guid", "message": "..."}
            keka_leave_id = str(keka_res.get("data") or "").strip()
            if not keka_leave_id and keka_res.get("succeeded"):
                keka_leave_id = f"KEKA-SYNCED-{leave_request.id}"

            leave_request.keka_leave_request_id = keka_leave_id or None
            leave_request.synced_to_keka = True
            leave_request.last_sync_error = None
            leave_request.last_synced_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(leave_request)

            logger.info(
                "Successfully pushed local leave ID %s to Keka (Keka ID: %s)",
                leave_request.id,
                keka_leave_id,
            )

            return {
                "success": True,
                "synced": True,
                "local_leave_id": leave_request.id,
                "keka_leave_request_id": keka_leave_id,
                "last_synced_at": leave_request.last_synced_at,
                "error": None,
                "message": "Leave request created successfully in Keka.",
            }

        except (KekaAuthError, KekaAPIError) as err:
            err_msg = str(err)
            logger.error(
                "Keka API error syncing leave %s to Keka: %s",
                leave_request.id,
                err_msg,
            )
            leave_request.synced_to_keka = False
            leave_request.last_sync_error = err_msg
            await db.commit()
            await db.refresh(leave_request)
            return {
                "success": False,
                "synced": False,
                "local_leave_id": leave_request.id,
                "keka_leave_request_id": None,
                "error": err_msg,
                "message": f"Failed to push leave to Keka: {err_msg}",
            }
        except Exception as err:
            err_msg = "An unexpected error occurred while communicating with Keka."
            logger.exception("Unexpected error syncing leave %s to Keka: %s", leave_request.id, err)
            leave_request.synced_to_keka = False
            leave_request.last_sync_error = err_msg
            await db.commit()
            await db.refresh(leave_request)
            return {
                "success": False,
                "synced": False,
                "local_leave_id": leave_request.id,
                "keka_leave_request_id": None,
                "error": err_msg,
                "message": err_msg,
            }

    @staticmethod
    async def sync_all_unsynced_leaves(db: AsyncSession) -> Dict[str, Any]:
        """
        Finds all local approved leave requests that have not yet been synced to Keka,
        and pushes them sequentially to ensure idempotency.
        """
        from app.modules.leave_requests.repository import LeaveRequestRepository

        unsynced_records = await LeaveRequestRepository.get_unsynced_leaves(db)
        results = []
        synced_count = 0
        failed_count = 0

        for record in unsynced_records:
            res = await KekaLeaveService.sync_leave_to_keka(db, record)
            results.append(res)
            if res.get("synced"):
                synced_count += 1
            else:
                failed_count += 1

        return {
            "total_found": len(unsynced_records),
            "synced_count": synced_count,
            "failed_count": failed_count,
            "details": results,
        }

    @staticmethod
    async def sync_leave_statuses_from_keka(
        db: AsyncSession,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Pulls leave requests from Keka and updates corresponding local LeaveRequest records'
        status (Pending, Approved, Rejected, Cancelled) if matched by keka_leave_request_id.
        """
        from app.modules.leave_requests.repository import LeaveRequestRepository

        raw_leaves = await KekaClient.get_all_pages(
            KekaClient.get_leave_requests,
            from_date=from_date,
            to_date=to_date,
        )

        status_mapping = {
            0: "Pending",
            1: "Approved",
            2: "Rejected",
            3: "Cancelled",
            "pending": "Pending",
            "approved": "Approved",
            "rejected": "Rejected",
            "cancelled": "Cancelled",
            "canceled": "Cancelled",
        }

        updated_count = 0
        matched_count = 0
        details = []

        for item in raw_leaves:
            keka_req_id = str(item.get("id") or item.get("leaveRequestId") or "").strip()
            if not keka_req_id:
                continue

            local_leave = await LeaveRequestRepository.get_by_keka_id(db, keka_req_id)
            if not local_leave:
                continue

            matched_count += 1
            raw_status = item.get("status")
            new_status = status_mapping.get(raw_status)
            if not new_status and isinstance(raw_status, str):
                new_status = status_mapping.get(raw_status.lower(), raw_status.title())

            if new_status and local_leave.status != new_status:
                old_status = local_leave.status
                local_leave.status = new_status
                local_leave.last_synced_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(local_leave)
                updated_count += 1
                details.append({
                    "local_leave_id": local_leave.id,
                    "keka_leave_request_id": keka_req_id,
                    "old_status": old_status,
                    "new_status": new_status,
                })

        return {
            "total_keka_records": len(raw_leaves),
            "matched_local_records": matched_count,
            "updated_count": updated_count,
            "details": details,
        }

