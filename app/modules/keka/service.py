import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.keka.model import KekaEmployeeMapping
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.users.model import User
from app.services.keka.keka_client import KekaClient

logger = logging.getLogger(__name__)


class KekaEmployeeMappingService:
    """Service handling read-only mapping inspection and preview logic."""

    @staticmethod
    async def list_mappings(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Tuple[List[KekaEmployeeMapping], int]:
        """Returns existing mappings from database."""
        return await KekaEmployeeMappingRepository.list_mappings(db, skip=skip, limit=limit)

    @staticmethod
    async def get_by_keka_employee_id(
        db: AsyncSession, keka_employee_id: str
    ) -> Optional[KekaEmployeeMapping]:
        """Returns single mapping by Keka employee UUID."""
        return await KekaEmployeeMappingRepository.get_by_keka_employee_id(
            db, keka_employee_id
        )

    @staticmethod
    async def get_mapping_preview(db: AsyncSession) -> Dict[str, Any]:
        """
        Purely READ-ONLY preview endpoint:
        Fetches employees from Keka API and classifies them against local users into:
        - 'mapped': Existing record in keka_employee_mappings table
        - 'local_match': Unmapped, but unique local user found by email or employee number
        - 'unmapped': No local user found
        - 'conflict': Ambiguous or clashing match (e.g. email matches user A, emp number matches user B, or user already mapped)

        STRICT SAFETY: Does NOT modify, insert, delete, or commit any records in PostgreSQL.
        """
        # 1. Fetch employees from Keka API (read-only)
        keka_data = await KekaClient.get_all_employees()
        keka_employees = keka_data.get("data", []) or []

        # 2. Fetch local users and existing mappings (read-only SELECTs)
        users_result = await db.execute(
            select(User).options(selectinload(User.role), selectinload(User.department))
        )
        local_users = list(users_result.scalars().all())

        mappings_result = await db.execute(
            select(KekaEmployeeMapping).options(selectinload(KekaEmployeeMapping.user))
        )
        existing_mappings = list(mappings_result.scalars().all())

        # 3. Build fast lookup dictionaries
        existing_by_keka_id = {m.keka_employee_id: m for m in existing_mappings}
        existing_by_user_id = {m.local_user_id: m for m in existing_mappings}
        users_by_id = {u.id: u for u in local_users}

        users_by_email: Dict[str, User] = {}
        for u in local_users:
            if u.email:
                users_by_email[u.email.strip().lower()] = u

        users_by_emp_number: Dict[str, User] = {}
        for u in local_users:
            if u.employee_id:
                users_by_emp_number[u.employee_id.strip()] = u

        # 4. Evaluate each Keka employee
        preview_items: List[Dict[str, Any]] = []
        summary = {"mapped": 0, "local_match": 0, "unmapped": 0, "conflict": 0}

        for emp in keka_employees:
            keka_id = str(emp.get("id") or "").strip()
            keka_email = (emp.get("email") or "").strip().lower()
            keka_emp_num = str(emp.get("employeeNumber") or "").strip()
            first_name = emp.get("firstName") or ""
            last_name = emp.get("lastName") or ""
            keka_name = emp.get("displayName") or f"{first_name} {last_name}".strip() or None

            raw_dept = emp.get("department")
            if isinstance(raw_dept, dict):
                dept_name = raw_dept.get("name") or raw_dept.get("title")
            else:
                dept_name = raw_dept or emp.get("departmentName")

            job_title = emp.get("jobTitle") or emp.get("designation")

            item: Dict[str, Any] = {
                "keka_employee_id": keka_id,
                "keka_employee_number": keka_emp_num or None,
                "keka_name": keka_name,
                "keka_email": keka_email or None,
                "keka_department": dept_name or None,
                "keka_job_title": job_title or None,
                "status": "unmapped",
                "matched_local_user_id": None,
                "matched_local_user_email": None,
                "matched_local_user_name": None,
                "matched_by": None,
                "reason": "",
            }

            # Case A: Existing mapping already recorded
            if keka_id in existing_by_keka_id:
                existing_map = existing_by_keka_id[keka_id]
                mapped_user = users_by_id.get(existing_map.local_user_id)
                if mapped_user:
                    item["status"] = "mapped"
                    item["matched_by"] = "existing_mapping"
                    item["matched_local_user_id"] = mapped_user.id
                    item["matched_local_user_email"] = mapped_user.email
                    item["matched_local_user_name"] = f"{mapped_user.first_name} {mapped_user.last_name}".strip()
                    item["reason"] = (
                        f"Active mapping exists for local user '{mapped_user.first_name} {mapped_user.last_name}' "
                        f"(ID: {mapped_user.id})."
                    )
                else:
                    item["status"] = "conflict"
                    item["matched_by"] = "existing_mapping"
                    item["reason"] = (
                        f"Mapping exists (ID: {existing_map.id}) but referenced local user ID "
                        f"{existing_map.local_user_id} does not exist in local database."
                    )
                summary[item["status"]] += 1
                preview_items.append(item)
                continue

            # Case B: Unmapped candidate — evaluate local matching
            cand_by_email = users_by_email.get(keka_email) if keka_email else None
            cand_by_emp_num = users_by_emp_number.get(keka_emp_num) if keka_emp_num else None

            # Conflict B1: Email and employee number point to different users
            if cand_by_email and cand_by_emp_num and cand_by_email.id != cand_by_emp_num.id:
                item["status"] = "conflict"
                item["reason"] = (
                    f"Ambiguous match: Email '{keka_email}' matches user ID {cand_by_email.id} "
                    f"('{cand_by_email.first_name} {cand_by_email.last_name}'), while employee number "
                    f"'{keka_emp_num}' matches user ID {cand_by_emp_num.id} "
                    f"('{cand_by_emp_num.first_name} {cand_by_emp_num.last_name}')."
                )
                summary["conflict"] += 1
                preview_items.append(item)
                continue

            # Check if matching user is already mapped to another Keka employee
            matched_cand = cand_by_email or cand_by_emp_num
            if matched_cand:
                existing_for_user = existing_by_user_id.get(matched_cand.id)
                if existing_for_user and existing_for_user.keka_employee_id != keka_id:
                    item["status"] = "conflict"
                    item["reason"] = (
                        f"Conflict: Local user '{matched_cand.first_name} {matched_cand.last_name}' "
                        f"(ID: {matched_cand.id}) is already mapped to a different Keka employee ID "
                        f"('{existing_for_user.keka_employee_id}')."
                    )
                    summary["conflict"] += 1
                    preview_items.append(item)
                    continue

                # Clean match found
                item["status"] = "local_match"
                item["matched_local_user_id"] = matched_cand.id
                item["matched_local_user_email"] = matched_cand.email
                item["matched_local_user_name"] = f"{matched_cand.first_name} {matched_cand.last_name}".strip()

                if cand_by_email:
                    item["matched_by"] = "email"
                    item["reason"] = (
                        f"Found unmapped local user '{matched_cand.first_name} {matched_cand.last_name}' "
                        f"matching email '{keka_email}'."
                    )
                else:
                    item["matched_by"] = "employee_number"
                    item["reason"] = (
                        f"Found unmapped local user '{matched_cand.first_name} {matched_cand.last_name}' "
                        f"matching employee number '{keka_emp_num}'."
                    )
                summary["local_match"] += 1
                preview_items.append(item)
                continue

            # Case C: Completely unmapped
            item["status"] = "unmapped"
            item["reason"] = "No matching local user found by email or employee number."
            summary["unmapped"] += 1
            preview_items.append(item)

        return {
            "total_keka_employees": len(keka_employees),
            "summary": summary,
            "items": preview_items,
        }

    @staticmethod
    async def save_mapping(
        db: AsyncSession,
        keka_employee_id: str,
        local_user_id: int,
        keka_employee_number: Optional[str] = None,
    ) -> KekaEmployeeMapping:
        """
        Creates or updates a 1:1 mapping between a local user and a Keka employee UUID.
        Validates that the local user exists and is not already mapped to another Keka employee.
        """
        clean_keka_id = keka_employee_id.strip()
        if not clean_keka_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keka employee ID cannot be empty.",
            )

        # 1. Verify local user exists
        user_res = await db.execute(select(User).where(User.id == local_user_id))
        user = user_res.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Local user with ID {local_user_id} does not exist.",
            )

        # 2. Check if local user is already mapped to a different Keka employee
        existing_for_user = await KekaEmployeeMappingRepository.get_by_local_user_id(db, local_user_id)
        if existing_for_user and existing_for_user.keka_employee_id != clean_keka_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"User '{user.first_name} {user.last_name}' (ID: {user.id}) is already mapped "
                    f"to Keka employee '{existing_for_user.keka_employee_id}'. Please remove the old mapping first."
                ),
            )

        # 3. Check if mapping for this keka_employee_id already exists
        existing_for_keka = await KekaEmployeeMappingRepository.get_by_keka_employee_id(db, clean_keka_id)
        if existing_for_keka:
            return await KekaEmployeeMappingRepository.update_mapping(
                db,
                existing_for_keka,
                local_user_id=local_user_id,
                keka_employee_number=keka_employee_number or existing_for_keka.keka_employee_number,
                sync_status="active",
            )

        return await KekaEmployeeMappingRepository.create_mapping(
            db,
            keka_employee_id=clean_keka_id,
            local_user_id=local_user_id,
            keka_employee_number=keka_employee_number,
            sync_status="active",
        )

    @staticmethod
    async def delete_mapping(db: AsyncSession, keka_employee_id: str) -> bool:
        """Removes a Keka employee mapping by Keka employee UUID."""
        mapping = await KekaEmployeeMappingRepository.get_by_keka_employee_id(db, keka_employee_id.strip())
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No mapping found for Keka employee ID '{keka_employee_id}'.",
            )
        return await KekaEmployeeMappingRepository.delete_mapping(db, mapping)

    @staticmethod
    async def auto_sync_matched(db: AsyncSession) -> Dict[str, Any]:
        """
        Executes auto-mapping for all candidates detected with status 'local_match'.
        Safely maps eligible users and skips unmapped or conflicted entries.
        """
        preview = await KekaEmployeeMappingService.get_mapping_preview(db)
        items = preview.get("items", [])

        mapped_count = 0
        mapped_records: List[Dict[str, Any]] = []
        skipped_count = 0

        for item in items:
            if item.get("status") == "local_match" and item.get("matched_local_user_id"):
                k_id = item["keka_employee_id"]
                u_id = item["matched_local_user_id"]
                emp_num = item.get("keka_employee_number")

                try:
                    await KekaEmployeeMappingService.save_mapping(
                        db,
                        keka_employee_id=k_id,
                        local_user_id=u_id,
                        keka_employee_number=emp_num,
                    )
                    mapped_count += 1
                    mapped_records.append({
                        "keka_employee_id": k_id,
                        "local_user_id": u_id,
                        "keka_name": item.get("keka_name"),
                        "matched_by": item.get("matched_by"),
                    })
                except Exception as ex:
                    logger.warning("Auto-sync skipped keka employee %s: %s", k_id, ex)
                    skipped_count += 1
            else:
                skipped_count += 1

        return {
            "mapped_count": mapped_count,
            "skipped_count": skipped_count,
            "total_evaluated": len(items),
            "mapped_items": mapped_records,
        }

    @staticmethod
    async def get_keka_leave_types() -> List[Dict[str, Any]]:
        """
        Fetches leave types configured in Keka via GET /time/leavetypes and normalizes the payload.
        """
        raw_res = await KekaClient.get_leave_types()
        items = raw_res.get("data") if isinstance(raw_res, dict) else raw_res
        if not isinstance(items, list):
            items = []

        normalized: List[Dict[str, Any]] = []
        for lt in items:
            if not isinstance(lt, dict):
                continue
            normalized.append({
                "id": str(lt.get("id") or "").strip(),
                "name": lt.get("name") or lt.get("title") or "Unnamed Leave Type",
                "code": lt.get("code") or None,
                "description": lt.get("description") or None,
            })
        return normalized

