import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.keka.model import KekaEmployeeMapping
from app.modules.leave_requests.model import LeaveRequest
from app.services.keka.keka_client import KekaClient

logger = logging.getLogger(__name__)


def _parse_iso_time(val: Any) -> Optional[str]:
    """Helper to extract HH:MM string from ISO or time strings."""
    if not val:
        return None
    s = str(val).strip()
    if "T" in s:
        try:
            # e.g. 2026-09-28T09:15:00
            t_part = s.split("T")[1].replace("Z", "")
            return t_part[:5]  # HH:MM
        except Exception:
            return s
    if ":" in s and len(s) >= 5:
        return s[:5]
    return s


def _normalize_status(raw_status: Any, first_in: Any, total_hours: float) -> str:
    """Normalizes Keka dayStatus into human-readable label."""
    if isinstance(raw_status, str) and raw_status.strip():
        s = raw_status.strip().title()
        if "Present" in s:
            return "Present"
        if "Absent" in s:
            return "Absent"
        if "Leave" in s:
            return "On Leave"
        if "Half" in s:
            return "Half Day"
        if "Holiday" in s:
            return "Holiday"
        if "Weekly" in s or "Weekend" in s or "Off" in s:
            return "Weekly Off"
        return s

    # Numeric status fallback in Keka (e.g. 1 = Present, 0 = Absent, 2 = HalfDay, etc.)
    if raw_status == 1 or (first_in and total_hours >= 4.0):
        return "Present"
    if raw_status == 2 or (first_in and 0 < total_hours < 4.0):
        return "Half Day"
    if raw_status == 0 or (not first_in and total_hours == 0):
        return "Absent"

    return "Present" if first_in else "Absent"


class KekaAttendanceService:
    """Service for pulling, normalizing, and auditing attendance records from Keka."""

    @classmethod
    async def get_attendance_records(
        cls,
        db: AsyncSession,
        from_date: str,
        to_date: str,
        employee_id: Optional[str] = None,
        only_mapped: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Pulls attendance records from Keka for the given date window and resolves
        each record to local Timesheet user mappings.
        """
        # 1. Fetch all local Keka employee mappings with preloaded user
        query = select(KekaEmployeeMapping).options(selectinload(KekaEmployeeMapping.user))
        result = await db.execute(query)
        mappings = list(result.scalars().all())

        mapping_by_keka_id: Dict[str, KekaEmployeeMapping] = {
            m.keka_employee_id: m for m in mappings if m.keka_employee_id
        }

        # 2. Call Keka API
        keka_emp_ids = [employee_id] if employee_id else None
        raw_records = await KekaClient.get_all_attendance(
            from_date=from_date,
            to_date=to_date,
            employee_ids=keka_emp_ids,
        )

        normalized_list: List[Dict[str, Any]] = []

        for r in raw_records:
            k_id = str(r.get("employeeId") or r.get("id") or "").strip()
            k_num = str(r.get("employeeNumber") or "").strip() or None
            k_name = str(r.get("employeeName") or r.get("name") or "").strip() or None

            mapping = mapping_by_keka_id.get(k_id)

            if only_mapped and not mapping:
                continue

            raw_date = str(r.get("attendanceDate") or r.get("date") or from_date).split("T")[0]
            first_in = _parse_iso_time(r.get("firstIn") or r.get("checkInTime") or r.get("inTime"))
            last_out = _parse_iso_time(r.get("lastOut") or r.get("checkOutTime") or r.get("outTime"))

            # Calculate or extract working hours
            eff_hrs = 0.0
            if "effectiveWorkingHours" in r and r["effectiveWorkingHours"] is not None:
                try:
                    eff_hrs = round(float(r["effectiveWorkingHours"]), 2)
                except (ValueError, TypeError):
                    eff_hrs = 0.0
            elif "totalWorkingHours" in r and r["totalWorkingHours"] is not None:
                try:
                    eff_hrs = round(float(r["totalWorkingHours"]), 2)
                except (ValueError, TypeError):
                    eff_hrs = 0.0

            gross_hrs = 0.0
            if "totalWorkingHours" in r and r["totalWorkingHours"] is not None:
                try:
                    gross_hrs = round(float(r["totalWorkingHours"]), 2)
                except (ValueError, TypeError):
                    gross_hrs = 0.0

            raw_status = r.get("dayStatus") or r.get("status")
            status = _normalize_status(raw_status, first_in, eff_hrs)

            # Detect missing punch (e.g. punched in but never punched out)
            is_missing_punch = bool(first_in and not last_out and status != "Weekly Off" and status != "Holiday")

            user_obj = mapping.user if mapping else None
            local_user_name = None
            if user_obj:
                local_user_name = f"{getattr(user_obj, 'first_name', '')} {getattr(user_obj, 'last_name', '')}".strip() or None

            normalized_list.append({
                "keka_employee_id": k_id,
                "keka_employee_number": k_num or (mapping.keka_employee_number if mapping else None),
                "keka_employee_name": k_name or local_user_name or "Unknown Employee",
                "date": raw_date,
                "status": status,
                "first_in": first_in,
                "last_out": last_out,
                "effective_hours": eff_hrs,
                "gross_hours": gross_hrs,
                "is_mapped": bool(mapping),
                "local_user_id": mapping.local_user_id if mapping else None,
                "local_user_name": local_user_name,
                "local_user_email": getattr(user_obj, "email", None) if user_obj else None,
                "is_missing_punch": is_missing_punch,
                "is_absent_without_leave": False,  # Cross-referenced in exceptions
            })

        return normalized_list

    @classmethod
    async def get_attendance_exceptions(
        cls,
        db: AsyncSession,
        check_date: str,
    ) -> Dict[str, Any]:
        """
        Cross-references attendance records for a specific date against local LeaveRequest records
        to identify attendance exceptions:
        1. Missing punch (punched in but no punch out)
        2. Absent without leave (Keka marked Absent, but employee has no approved local leave)
        """
        # Pull attendance for single date
        records = await cls.get_attendance_records(
            db=db,
            from_date=check_date,
            to_date=check_date,
            only_mapped=False,
        )

        # Parse date
        target_date = datetime.strptime(check_date, "%Y-%m-%d").date()

        # Query local approved/pending leave requests that cover this date
        leave_query = select(LeaveRequest).where(
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date,
            LeaveRequest.status.in_(["approved", "pending"]),
        )
        leave_res = await db.execute(leave_query)
        active_leaves = list(leave_res.scalars().all())
        user_ids_with_leave = {lv.user_id for lv in active_leaves}

        exceptions: List[Dict[str, Any]] = []
        missing_punch_count = 0
        absent_no_leave_count = 0

        for r in records:
            is_missing = r["is_missing_punch"]
            local_user_id = r.get("local_user_id")

            # Check absent without leave
            is_absent_no_leave = False
            if r["status"] == "Absent" and local_user_id:
                if local_user_id not in user_ids_with_leave:
                    is_absent_no_leave = True
                    r["is_absent_without_leave"] = True

            if is_missing:
                missing_punch_count += 1
            if is_absent_no_leave:
                absent_no_leave_count += 1

            if is_missing or is_absent_no_leave:
                exceptions.append({
                    **r,
                    "exception_type": "missing_punch" if is_missing else "absent_without_leave",
                    "exception_note": "Missing clock-out punch" if is_missing else "Marked absent without active local leave request",
                })

        return {
            "date": check_date,
            "total_evaluated": len(records),
            "exceptions_count": len(exceptions),
            "missing_punch_count": missing_punch_count,
            "absent_without_leave_count": absent_no_leave_count,
            "items": exceptions,
        }

    @classmethod
    async def push_time_entry_for_user(
        cls,
        db: AsyncSession,
        user_id: int,
        timestamp: datetime,
        punch_status: int = 0,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves a local user_id to their Keka employee UUID and logs an attendance punch
        in Keka via POST /attendance/employee/{routeEmployeeId}/timeentry.
        """
        from app.modules.keka.repository import KekaEmployeeMappingRepository
        from app.modules.keka.leave_service import KekaMappingNotFoundError

        mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
        if not mapping or not mapping.keka_employee_id:
            raise KekaMappingNotFoundError(user_id=user_id)

        route_employee_id = mapping.keka_employee_id.strip()
        iso_timestamp = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)

        res = await KekaClient.log_attendance_time_entry(
            route_employee_id=route_employee_id,
            timestamp=iso_timestamp,
            punch_status=punch_status,
            note=note or f"Punch logged from Timesheet Portal for user {user_id}",
        )
        return {
            "success": True,
            "local_user_id": user_id,
            "keka_employee_id": route_employee_id,
            "timestamp": iso_timestamp,
            "punch_status": punch_status,
            "keka_response": res,
        }

    @classmethod
    async def sync_weekly_off_policy_to_calendar(
        cls,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Pulls weekly off policies from Keka and updates the company WorkingCalendar working_days JSON.
        If a day is defined as a weekly off in the active Keka policy, working_days[day] is set to False;
        otherwise True.
        """
        from app.modules.working_calendar.service import WorkingCalendarService
        from app.modules.working_calendar.schema import WorkingCalendarUpdate

        policies_data = await KekaClient.get_weekly_off_policies()
        policies = policies_data if isinstance(policies_data, list) else policies_data.get("data", [])
        if not policies and isinstance(policies_data, dict):
            policies = [policies_data]

        if not policies:
            return {
                "success": False,
                "message": "No weekly off policies returned by Keka",
                "updated": False,
            }

        # Take first/primary weekly off policy
        primary_policy = policies[0] if isinstance(policies, list) else policies

        # Determine weekly off days from policy
        off_days = set()
        if isinstance(primary_policy, dict):
            raw_days = primary_policy.get("weeklyOffDays") or primary_policy.get("offDays") or []
            if isinstance(raw_days, list):
                for d in raw_days:
                    if isinstance(d, str):
                        off_days.add(d.lower())
                    elif isinstance(d, dict) and "day" in d:
                        off_days.add(str(d["day"]).lower())
            elif isinstance(raw_days, str):
                off_days.add(raw_days.lower())

        # Fallback default: if off_days was not parsed, default standard weekend
        if not off_days:
            off_days = {"saturday", "sunday"}

        calendar_days = {
            "monday": "monday" not in off_days,
            "tuesday": "tuesday" not in off_days,
            "wednesday": "wednesday" not in off_days,
            "thursday": "thursday" not in off_days,
            "friday": "friday" not in off_days,
            "saturday": "saturday" not in off_days,
            "sunday": "sunday" not in off_days,
        }

        calendar = await WorkingCalendarService.get_config(db)
        old_working_days = dict(calendar.working_days) if calendar.working_days else {}

        update_dto = WorkingCalendarUpdate(working_days=calendar_days)
        updated_cal = await WorkingCalendarService.update_config(db, update_dto)

        return {
            "success": True,
            "policy_id": primary_policy.get("id") if isinstance(primary_policy, dict) else None,
            "policy_name": primary_policy.get("name") if isinstance(primary_policy, dict) else None,
            "off_days": list(off_days),
            "old_working_days": old_working_days,
            "new_working_days": updated_cal.working_days,
        }

