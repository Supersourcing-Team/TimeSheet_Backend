import asyncio
import logging
import uuid
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
    def __init__(self, user_id: int, message: Optional[str] = None):
        self.user_id = user_id
        super().__init__(
            message
            or f"No Keka employee mapping found for local user ID {user_id}. Please map the employee first."
        )


class KekaLeaveService:
    _sync_locks: Dict[int, asyncio.Lock] = {}
    _sync_locks_mutex = asyncio.Lock()

    @classmethod
    async def _get_leave_lock(cls, leave_id: int) -> asyncio.Lock:
        async with cls._sync_locks_mutex:
            if leave_id not in cls._sync_locks:
                cls._sync_locks[leave_id] = asyncio.Lock()
            return cls._sync_locks[leave_id]

    @staticmethod
    async def get_keka_employee_id_for_user(db: AsyncSession, user_id: int) -> str:
        mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
        if not mapping or not mapping.keka_employee_id:
            raise KekaMappingNotFoundError(user_id=user_id)
        return mapping.keka_employee_id.strip()

    @classmethod
    async def sync_leave_to_keka(
        cls,
        db: AsyncSession,
        leave_request: LeaveRequest,
        keka_leave_type_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        lock = await cls._get_leave_lock(leave_request.id)
        async with lock:
            if hasattr(db, "refresh"):
                try:
                    await db.refresh(leave_request)
                except Exception:
                    pass

            if leave_request.synced_to_keka and leave_request.keka_leave_request_id:
                return {
                    "success": True,
                    "synced": True,
                    "local_leave_id": leave_request.id,
                    "keka_leave_request_id": leave_request.keka_leave_request_id,
                    "last_synced_at": leave_request.last_synced_at,
                    "error": None,
                    "message": "Leave request is already synchronized to Keka.",
                }

            if leave_request.leave_duration_type == "partial_day":
                err_msg = "Partial-day / hourly leaves are managed locally and cannot be synchronized to Keka."
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

            if leave_request.leave_duration_type == "half_day" and leave_request.start_date != leave_request.end_date:
                err_msg = "Half-day leaves cannot span multiple dates in Keka."
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
                or getattr(settings, "KEKA_DEFAULT_LEAVE_TYPE_ID", None)
                or ""
            ).strip()

            if not leave_type_to_use:
                err_msg = f"No Keka leave type ID mapped for leave type {leave_request.leave_type_id}. Please map the leave type to Keka first."
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

            from_date_str = f"{leave_request.start_date.isoformat()}T00:00:00Z"
            to_date_str = f"{leave_request.end_date.isoformat()}T00:00:00Z"

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

                raw_data = keka_res.get("data") if isinstance(keka_res, dict) else None
                keka_leave_id = str(raw_data or "").strip()
                is_valid_guid = False
                if keka_leave_id and isinstance(keka_res, dict) and keka_res.get("succeeded") is True:
                    try:
                        parsed_uuid = uuid.UUID(keka_leave_id)
                        is_valid_guid = True
                        keka_leave_id = str(parsed_uuid)
                    except (ValueError, TypeError, AttributeError):
                        is_valid_guid = False

                if not is_valid_guid:
                    err_msg = "Keka response did not contain a valid leave request ID."
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

                leave_request.keka_leave_request_id = keka_leave_id
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

            item_emp_id = str(item.get("employeeId") or "").strip().lower()
            if item_emp_id:
                user_mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, local_leave.user_id)
                if not user_mapping or user_mapping.keka_employee_id.strip().lower() != item_emp_id:
                    logger.warning(
                        "Mismatched employee for Keka leave %s: expected %s, got %s",
                        keka_req_id,
                        getattr(user_mapping, "keka_employee_id", None),
                        item_emp_id,
                    )
                    continue

            matched_count += 1
            raw_status = item.get("status")
            new_status = None
            try:
                new_status = status_mapping.get(raw_status)
            except TypeError:
                new_status = None
            if not new_status and isinstance(raw_status, str):
                new_status = status_mapping.get(raw_status.lower().strip())

            if not new_status:
                logger.warning(
                    "Unknown or unsupported Keka status '%s' for leave request %s; leaving local status unchanged.",
                    raw_status,
                    keka_req_id,
                )
                continue

            if local_leave.status == "Cancelled" and new_status != "Cancelled":
                local_leave.last_sync_error = f"Leave is cancelled locally, but remains {new_status} in Keka HR."
                local_leave.last_synced_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(local_leave)
                continue

            if local_leave.status != new_status:
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

