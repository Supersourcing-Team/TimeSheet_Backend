import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.keka.model import KekaEmployeeMapping
from app.modules.keka.repository import KekaEmployeeMappingRepository
from app.modules.keka.schema import (
    KekaEmployeeCreateRequest,
    KekaEmployeeExitRequest,
    KekaJobDetailsUpdateRequest,
    KekaODCreateRequest,
    KekaWFHCreateRequest,
)
from app.modules.users.model import User
from app.services.keka.keka_client import KekaAPIError, KekaClient

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
            dept_name = None
            if isinstance(raw_dept, dict):
                dept_name = raw_dept.get("name") or raw_dept.get("title")
            elif isinstance(raw_dept, str) and raw_dept:
                dept_name = raw_dept
            elif emp.get("departmentName"):
                dept_name = emp.get("departmentName")
            else:
                for g in emp.get("groups", []):
                    if isinstance(g, dict) and g.get("groupType") == 2:
                        dept_name = g.get("title") or g.get("name")
                        break

            raw_job = emp.get("jobTitle") or emp.get("designation")
            if isinstance(raw_job, dict):
                job_title = raw_job.get("title") or raw_job.get("name")
            else:
                job_title = raw_job

            raw_join = emp.get("joiningDate") or emp.get("dateOfJoining") or emp.get("hireDate")
            date_of_joining = str(raw_join)[:10] if raw_join else None

            raw_status = emp.get("employmentStatus")
            status_map = {0: "Working", 1: "Relieved", 2: "Notice Period", 3: "Probation"}
            employment_status = status_map.get(raw_status, str(raw_status) if raw_status is not None else "Active")

            item: Dict[str, Any] = {
                "keka_employee_id": keka_id,
                "keka_employee_number": keka_emp_num or None,
                "keka_name": keka_name,
                "keka_email": keka_email or None,
                "keka_department": dept_name or None,
                "keka_job_title": job_title or None,
                "date_of_joining": date_of_joining,
                "employment_status": employment_status,
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

    @staticmethod
    async def sync_employees_from_keka(
        db: AsyncSession,
        update_existing: bool = True,
        create_missing: bool = False,
        keka_employee_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deep business flow integration: Synchronizes Keka employee records into local database.
        - Matches existing local users by KekaEmployeeMapping, email, or employee number.
        - Updates user names, employment status (e.g. Relieved/Exited -> Inactive), and joining date.
        - Resolves and links department_id from local departments table.
        - Creates 1:1 mapping in keka_employee_mappings.
        - If create_missing is True, provisions missing users with default Employee role.
        - Does NOT create duplicate users or overwrite roles/passwords.
        """
        from datetime import datetime, timezone, date
        from app.modules.departments.model import Department
        from app.modules.roles.model import Role

        # 1. Fetch all Keka employees
        keka_data = await KekaClient.get_all_employees()
        keka_employees = keka_data.get("data", []) or []
        if keka_employee_id:
            keka_employees = [e for e in keka_employees if str(e.get("id") or "").strip() == keka_employee_id.strip()]

        # 2. Fetch local entities
        users_res = await db.execute(
            select(User).options(selectinload(User.role), selectinload(User.department), selectinload(User.keka_mapping))
        )
        local_users = list(users_res.scalars().all())

        depts_res = await db.execute(select(Department))
        local_departments = list(depts_res.scalars().all())
        dept_by_name = {d.name.strip().lower(): d for d in local_departments if d.name}

        role_res = await db.execute(select(Role).where(Role.name == "Employee"))
        default_role = role_res.scalar_one_or_none()
        if not default_role:
            first_role_res = await db.execute(select(Role).limit(1))
            default_role = first_role_res.scalar_one_or_none()

        mappings_res = await db.execute(select(KekaEmployeeMapping))
        existing_mappings = list(mappings_res.scalars().all())
        mapping_by_keka_id = {m.keka_employee_id: m for m in existing_mappings if m.keka_employee_id}
        mapping_by_user_id = {m.local_user_id: m for m in existing_mappings}

        user_by_id = {u.id: u for u in local_users}
        user_by_email = {u.email.strip().lower(): u for u in local_users if u.email}
        user_by_emp_num = {u.employee_id.strip(): u for u in local_users if u.employee_id}

        updated_count = 0
        created_count = 0
        mapped_count = 0
        skipped_count = 0
        conflicts_count = 0
        details = []

        now_utc = datetime.now(timezone.utc)

        for emp in keka_employees:
            k_id = str(emp.get("id") or "").strip()
            if not k_id:
                continue

            k_email = (emp.get("email") or "").strip().lower()
            k_emp_num = str(emp.get("employeeNumber") or "").strip()
            first_name = (emp.get("firstName") or "").strip()
            last_name = (emp.get("lastName") or "").strip()
            raw_status = emp.get("employmentStatus") or emp.get("status")

            # Determine local status
            if raw_status in (1, "Relieved", "Exited", "Terminated", "Inactive"):
                local_status = "Inactive"
            elif raw_status in (2, "Notice Period", "NoticePeriod"):
                local_status = "Notice Period"
            else:
                local_status = "Active"

            # Parse joining date
            parsed_joining_date = None
            raw_join = emp.get("joiningDate") or emp.get("dateOfJoining") or emp.get("hireDate")
            if raw_join:
                try:
                    parsed_joining_date = datetime.fromisoformat(str(raw_join).replace("Z", "+00:00")).date()
                except Exception:
                    pass

            # Resolve department
            raw_dept = emp.get("department")
            dept_name_str = ""
            if isinstance(raw_dept, dict):
                dept_name_str = (raw_dept.get("name") or raw_dept.get("title") or "").strip().lower()
            elif isinstance(raw_dept, str) and raw_dept:
                dept_name_str = raw_dept.strip().lower()
            elif emp.get("departmentName"):
                dept_name_str = str(emp.get("departmentName")).strip().lower()
            else:
                for g in emp.get("groups", []):
                    if isinstance(g, dict) and g.get("groupType") == 2:
                        dept_name_str = (g.get("title") or g.get("name") or "").strip().lower()
                        break

            matched_dept = dept_by_name.get(dept_name_str) if dept_name_str else None
            if not matched_dept and dept_name_str:
                new_dept = Department(
                    name=dept_name_str.title(),
                    code=dept_name_str[:6].upper(),
                    is_active=True
                )
                db.add(new_dept)
                await db.flush()
                dept_by_name[dept_name_str] = new_dept
                matched_dept = new_dept

            # Check if already mapped
            existing_map = mapping_by_keka_id.get(k_id)
            target_user = None

            if existing_map:
                target_user = user_by_id.get(existing_map.local_user_id)
            else:
                # Candidate lookup by email, then employee number
                cand_email = user_by_email.get(k_email) if k_email else None
                cand_num = user_by_emp_num.get(k_emp_num) if k_emp_num else None

                if cand_email and cand_num and cand_email.id != cand_num.id:
                    conflicts_count += 1
                    details.append({"keka_id": k_id, "action": "conflict", "reason": "Email and employee number match different users"})
                    continue

                candidate = cand_email or cand_num
                if candidate:
                    if candidate.id in mapping_by_user_id and mapping_by_user_id[candidate.id].keka_employee_id != k_id:
                        conflicts_count += 1
                        details.append({"keka_id": k_id, "action": "conflict", "reason": "User already mapped to another Keka ID"})
                        continue
                    target_user = candidate

            if target_user:
                # Update existing user if enabled
                if update_existing:
                    if first_name:
                        target_user.first_name = first_name
                    if last_name:
                        target_user.last_name = last_name
                    if parsed_joining_date:
                        target_user.joining_date = parsed_joining_date
                    if local_status:
                        target_user.status = local_status
                    if matched_dept:
                        target_user.department_id = matched_dept.id

                    updated_count += 1

                # Ensure mapping exists and is up to date
                if not existing_map:
                    mapping = KekaEmployeeMapping(
                        keka_employee_id=k_id,
                        local_user_id=target_user.id,
                        keka_employee_number=k_emp_num or None,
                        sync_status="active",
                        last_synced_at=now_utc,
                    )
                    db.add(mapping)
                    mapping_by_keka_id[k_id] = mapping
                    mapping_by_user_id[target_user.id] = mapping
                    mapped_count += 1
                else:
                    existing_map.keka_employee_number = k_emp_num or existing_map.keka_employee_number
                    existing_map.last_synced_at = now_utc
                    existing_map.sync_status = "active" if local_status != "Inactive" else "inactive"

                details.append({"keka_id": k_id, "user_id": target_user.id, "action": "updated_and_mapped"})

            elif create_missing and k_email and k_email not in user_by_email:
                # Provision new user safely
                assigned_emp_id = k_emp_num or f"KEKA-{k_id[:8]}"
                if assigned_emp_id in user_by_emp_num:
                    assigned_emp_id = f"EMP-{len(local_users) + created_count + 1}"

                new_user = User(
                    email=k_email,
                    first_name=first_name or "Keka",
                    last_name=last_name or "Employee",
                    employee_id=assigned_emp_id,
                    role_id=default_role.id if default_role else 1,
                    department_id=matched_dept.id if matched_dept else None,
                    joining_date=parsed_joining_date or date.today(),
                    status=local_status,
                )
                db.add(new_user)
                await db.flush()  # to obtain new_user.id

                mapping = KekaEmployeeMapping(
                    keka_employee_id=k_id,
                    local_user_id=new_user.id,
                    keka_employee_number=k_emp_num or None,
                    sync_status="active",
                    last_synced_at=now_utc,
                )
                db.add(mapping)

                user_by_id[new_user.id] = new_user
                user_by_email[k_email] = new_user
                user_by_emp_num[assigned_emp_id] = new_user
                mapping_by_keka_id[k_id] = mapping
                mapping_by_user_id[new_user.id] = mapping

                created_count += 1
                details.append({"keka_id": k_id, "user_id": new_user.id, "action": "created_user_and_mapping"})
            else:
                skipped_count += 1

        await db.commit()

        return {
            "total_keka_employees": len(keka_employees),
            "updated_count": updated_count,
            "created_count": created_count,
            "mapped_count": mapped_count,
            "skipped_count": skipped_count,
            "conflicts_count": conflicts_count,
            "items": details[:50],  # sample details
        }

    @staticmethod
    async def sync_departments_from_keka(db: AsyncSession) -> Dict[str, Any]:
        """
        Deep business flow integration: Pulls departments from Keka API and synchronizes
        them into the local departments table. Prevents duplicate department entries.
        """
        from app.modules.departments.model import Department

        raw_data = await KekaClient.get_departments(page_size=200)
        items = raw_data.get("data", []) or []

        existing_res = await db.execute(select(Department))
        local_depts = list(existing_res.scalars().all())
        existing_by_name = {d.name.strip().lower(): d for d in local_depts if d.name}

        created_count = 0
        existing_count = 0
        synced_items = []

        for d in items:
            name = (d.get("name") or d.get("title") or "").strip()
            if not name:
                continue

            normalized_key = name.lower()
            if normalized_key in existing_by_name:
                existing_dept = existing_by_name[normalized_key]
                existing_count += 1
                synced_items.append({"id": existing_dept.id, "name": existing_dept.name, "status": "existing"})
            else:
                code_cand = (d.get("code") or name[:4].upper()).strip()
                new_dept = Department(
                    name=name,
                    code=code_cand,
                    description=f"Synchronized from Keka HR ({d.get('id', '')})",
                    is_active=True,
                )
                db.add(new_dept)
                await db.flush()
                existing_by_name[normalized_key] = new_dept
                created_count += 1
                synced_items.append({"id": new_dept.id, "name": new_dept.name, "status": "created"})

        await db.commit()

        return {
            "total_keka_departments": len(items),
            "created_count": created_count,
            "existing_count": existing_count,
            "items": synced_items,
        }

    @staticmethod
    async def sync_leave_types_from_keka(db: AsyncSession) -> Dict[str, Any]:
        """
        Deep business flow integration: Pulls Keka configured leave types and matches them
        to local leave_types, setting keka_leave_type_id to guarantee seamless leave sync.
        """
        from app.modules.leave_types.model import LeaveType

        keka_types = await KekaEmployeeMappingService.get_keka_leave_types()

        local_res = await db.execute(select(LeaveType))
        local_types = list(local_res.scalars().all())
        local_by_code = {lt.code.strip().upper(): lt for lt in local_types if lt.code}
        local_by_name = {lt.name.strip().lower(): lt for lt in local_types if lt.name}

        matched_count = 0
        unmatched_count = 0
        results = []

        for kt in keka_types:
            k_id = kt["id"]
            k_name = (kt.get("name") or "").strip()
            k_code = (kt.get("code") or "").strip().upper()

            matched = None
            if k_code and k_code in local_by_code:
                matched = local_by_code[k_code]
            elif k_name and k_name.lower() in local_by_name:
                matched = local_by_name[k_name.lower()]

            if matched:
                matched.keka_leave_type_id = k_id
                matched_count += 1
                results.append({
                    "local_id": matched.id,
                    "local_name": matched.name,
                    "keka_id": k_id,
                    "keka_name": k_name,
                    "matched": True,
                })
            else:
                unmatched_count += 1
                results.append({
                    "keka_id": k_id,
                    "keka_name": k_name,
                    "matched": False,
                })

        await db.commit()

        return {
            "total_keka_leave_types": len(keka_types),
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "items": results,
        }

    @staticmethod
    async def sync_holidays_from_keka(
        db: AsyncSession, calendar_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deep business flow integration: Pulls holiday calendar from Keka API and synchronizes
        holidays into the local holidays table without duplicate entries.
        """
        from datetime import datetime
        from app.modules.holidays.model import Holiday
        from app.modules.holidays.repository import HolidayRepository

        # 1. Resolve calendar ID if not provided
        target_cal_id = calendar_id
        if not target_cal_id:
            cals = await KekaClient.get_holiday_calendars()
            cal_data = cals.get("data", []) or []
            if cal_data and isinstance(cal_data[0], dict):
                target_cal_id = str(cal_data[0].get("id") or "").strip()

        if not target_cal_id:
            return {"synced_count": 0, "message": "No Keka holiday calendar available to sync."}

        # 2. Fetch holidays for the calendar
        holidays_res = await KekaClient.get_calendar_holidays(target_cal_id)
        holidays_list = holidays_res.get("data", []) or []

        created_count = 0
        skipped_count = 0
        items = []

        for h in holidays_list:
            raw_date = h.get("date") or h.get("holidayDate") or h.get("startDate")
            name = (h.get("name") or h.get("title") or "Holiday").strip()
            if not raw_date:
                continue

            try:
                dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).date()
            except Exception:
                continue

            # Check if holiday exists for this date
            existing = await HolidayRepository.get_by_date(db, dt)
            if existing:
                skipped_count += 1
                items.append({"date": dt.isoformat(), "name": name, "status": "already_exists"})
            else:
                new_hol = Holiday(
                    date=dt,
                    name=name,
                    type="National",
                    description=h.get("description") or f"Synced from Keka Holiday Calendar ({target_cal_id})",
                    is_mandatory=True,
                )
                db.add(new_hol)
                created_count += 1
                items.append({"date": dt.isoformat(), "name": name, "status": "created"})

        await db.commit()

        return {
            "calendar_id": target_cal_id,
            "total_keka_holidays": len(holidays_list),
            "created_count": created_count,
            "skipped_existing_count": skipped_count,
            "items": items,
        }

    @staticmethod
    async def create_employee_flow(
        db: AsyncSession,
        payload: KekaEmployeeCreateRequest,
        create_local_user: bool = True,
    ) -> Dict[str, Any]:
        """
        Complete End-to-End Write Flow for Employee Creation:
        1. Formats validated Keka request payload adhering to OpenAPI /hris/employees.
        2. Calls KekaClient.create_employee(payload).
        3. Extracts Keka employee identifier (UUID) from response.data.
        4. When create_local_user=True:
           - Checks if local user with email or employee_id exists; updates if present or creates new User.
           - Resolves department_id from local departments table if department name provided.
           - Creates/updates keka_employee_mappings entry binding local_user_id <-> keka_employee_id.
           - Commits transaction to ensure consistency.
        5. Returns structured response with local_user_id, keka_employee_id, and sync status.
        """
        from datetime import datetime, timezone, date
        from app.modules.departments.model import Department
        from app.modules.roles.model import Role

        # 1. Format payload for Keka
        keka_payload = payload.model_dump(exclude_unset=True)

        # 2. Call Keka API
        keka_res = await KekaClient.create_employee(keka_payload)

        # 3. Extract Keka employee identifier
        keka_emp_id = str(keka_res.get("data") or "").strip()
        if not keka_emp_id and isinstance(keka_res, dict):
            if isinstance(keka_res.get("data"), dict):
                keka_emp_id = str(keka_res["data"].get("id") or "").strip()
            elif keka_res.get("id"):
                keka_emp_id = str(keka_res.get("id") or "").strip()

        if not keka_emp_id:
            raise KekaAPIError(
                f"Keka employee creation did not return a valid employee identifier: {keka_res.get('message', 'Unknown error')}",
                details=keka_res,
            )

        local_user = None
        mapping = None

        if create_local_user:
            now_utc = datetime.now(timezone.utc)
            email = (payload.email or "").strip().lower()
            emp_number = (payload.employeeNumber or "").strip()

            # Find existing local user
            if email:
                u_res = await db.execute(select(User).where(User.email == email))
                local_user = u_res.scalar_one_or_none()

            if not local_user and emp_number:
                u_res = await db.execute(select(User).where(User.employee_id == emp_number))
                local_user = u_res.scalar_one_or_none()

            # Resolve department
            matched_dept = None
            if payload.department:
                d_res = await db.execute(select(Department).where(Department.name.ilike(payload.department.strip())))
                matched_dept = d_res.scalar_one_or_none()

            # Parse joining date
            parsed_joining_date = None
            if payload.dateJoined:
                try:
                    parsed_joining_date = datetime.fromisoformat(payload.dateJoined.replace("Z", "+00:00")).date()
                except Exception:
                    parsed_joining_date = date.today()

            if local_user:
                # Update existing user
                if payload.firstName:
                    local_user.first_name = payload.firstName
                if payload.lastName:
                    local_user.last_name = payload.lastName
                if matched_dept:
                    local_user.department_id = matched_dept.id
                if parsed_joining_date:
                    local_user.joining_date = parsed_joining_date
                local_user.status = "Active"
            else:
                # Get default role
                r_res = await db.execute(select(Role).where(Role.name == "Employee"))
                role_obj = r_res.scalar_one_or_none()
                role_id = role_obj.id if role_obj else 2

                assigned_emp_id = emp_number or f"EMP-{keka_emp_id[:8]}"
                local_user = User(
                    email=email or f"user_{keka_emp_id[:8]}@timesheet.local",
                    first_name=payload.firstName or payload.displayName or "Keka",
                    last_name=payload.lastName or "Employee",
                    employee_id=assigned_emp_id,
                    role_id=role_id,
                    department_id=matched_dept.id if matched_dept else None,
                    joining_date=parsed_joining_date or date.today(),
                    status="Active",
                )
                db.add(local_user)
                await db.flush()

            # Link or create mapping in keka_employee_mappings
            m_res = await db.execute(
                select(KekaEmployeeMapping).where(
                    (KekaEmployeeMapping.keka_employee_id == keka_emp_id) |
                    (KekaEmployeeMapping.local_user_id == local_user.id)
                )
            )
            mapping = m_res.scalar_one_or_none()

            if mapping:
                mapping.keka_employee_id = keka_emp_id
                mapping.keka_employee_number = emp_number or mapping.keka_employee_number
                mapping.sync_status = "active"
                mapping.last_synced_at = now_utc
            else:
                mapping = KekaEmployeeMapping(
                    keka_employee_id=keka_emp_id,
                    local_user_id=local_user.id,
                    keka_employee_number=emp_number or None,
                    sync_status="active",
                    last_synced_at=now_utc,
                )
                db.add(mapping)

            await db.commit()
            await db.refresh(local_user)
            await db.refresh(mapping)

        return {
            "success": True,
            "keka_employee_id": keka_emp_id,
            "local_user_id": local_user.id if local_user else None,
            "employee_number": payload.employeeNumber,
            "email": payload.email,
            "keka_response": keka_res,
            "message": "Employee created in Keka and synchronized to local database.",
        }

    @staticmethod
    async def update_employee_job_details_flow(
        db: AsyncSession,
        payload: KekaJobDetailsUpdateRequest,
        user_id: Optional[int] = None,
        keka_employee_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete End-to-End Write Flow for Updating Employee Job Details:
        1. Resolves Keka employee UUID (from keka_employee_id or user_id via mapping).
        2. Calls KekaClient.update_employee_job_details(keka_employee_id, payload).
        3. Updates local User record if user_id or mapped user is found.
        4. Commits changes and returns response.
        """
        from app.modules.keka.leave_service import KekaMappingNotFoundError

        effective_user_id = user_id or payload.user_id
        target_keka_id = (keka_employee_id or payload.employeeId or "").strip()
        local_user = None

        if effective_user_id:
            mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, effective_user_id)
            if not mapping or not mapping.keka_employee_id:
                raise KekaMappingNotFoundError(user_id=effective_user_id)
            target_keka_id = mapping.keka_employee_id.strip()
            u_res = await db.execute(select(User).where(User.id == effective_user_id))
            local_user = u_res.scalar_one_or_none()
        elif target_keka_id:
            mapping = await KekaEmployeeMappingRepository.get_by_keka_employee_id(db, target_keka_id)
            if mapping and mapping.local_user_id:
                u_res = await db.execute(select(User).where(User.id == mapping.local_user_id))
                local_user = u_res.scalar_one_or_none()

        if not target_keka_id:
            raise HTTPException(status_code=400, detail="Either user_id or valid Keka employee UUID is required.")

        # Strip non-Keka PUT payload attributes
        keka_payload = payload.model_dump(exclude_unset=True)
        for non_keka_field in ("employeeId", "user_id", "secondaryJobTitle", "reportsToEmail"):
            keka_payload.pop(non_keka_field, None)

        res = await KekaClient.update_employee_job_details(employee_id=target_keka_id, payload=keka_payload)

        if local_user:
            if payload.employeeNumber:
                local_user.employee_id = payload.employeeNumber
            if payload.department:
                from app.modules.departments.model import Department
                d_res = await db.execute(select(Department).where(Department.name.ilike(payload.department.strip())))
                matched_d = d_res.scalar_one_or_none()
                if matched_d:
                    local_user.department_id = matched_d.id
            await db.commit()

        return {
            "success": True,
            "keka_employee_id": target_keka_id,
            "local_user_id": local_user.id if local_user else None,
            "keka_response": res,
            "message": "Employee job details updated successfully in Keka.",
        }

    @staticmethod
    async def create_employee_exit_flow(
        db: AsyncSession,
        payload: KekaEmployeeExitRequest,
        user_id: Optional[int] = None,
        keka_employee_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete End-to-End Write Flow for Employee Exit / Offboarding:
        1. Resolves Keka employee UUID (from keka_employee_id or user_id via mapping).
        2. Calls KekaClient.create_employee_exit_request(keka_employee_id, payload).
        3. Updates local User.status = 'Inactive' and mapping.sync_status = 'inactive'.
        4. Commits changes and returns response.
        """
        from datetime import datetime, timezone
        from app.modules.keka.leave_service import KekaMappingNotFoundError

        target_keka_id = (keka_employee_id or "").strip()
        local_user = None
        mapping = None

        if user_id:
            mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
            if not mapping or not mapping.keka_employee_id:
                raise KekaMappingNotFoundError(user_id=user_id)
            target_keka_id = mapping.keka_employee_id.strip()
            u_res = await db.execute(select(User).where(User.id == user_id))
            local_user = u_res.scalar_one_or_none()
        elif target_keka_id:
            mapping = await KekaEmployeeMappingRepository.get_by_keka_employee_id(db, target_keka_id)
            if mapping and mapping.local_user_id:
                u_res = await db.execute(select(User).where(User.id == mapping.local_user_id))
                local_user = u_res.scalar_one_or_none()

        if not target_keka_id:
            raise HTTPException(status_code=400, detail="Either user_id or valid Keka employee UUID is required.")

        keka_payload = payload.model_dump(exclude_unset=True)
        res = await KekaClient.create_employee_exit_request(employee_id=target_keka_id, payload=keka_payload)

        # Deactivate local user and mapping
        if local_user:
            local_user.status = "Inactive"
        if mapping:
            mapping.sync_status = "inactive"
            mapping.last_synced_at = datetime.now(timezone.utc)

        await db.commit()

        return {
            "success": True,
            "keka_employee_id": target_keka_id,
            "local_user_id": local_user.id if local_user else None,
            "keka_response": res,
            "message": "Employee exit request submitted in Keka and local user set to Inactive.",
        }

    @staticmethod
    async def create_wfh_flow(
        db: AsyncSession,
        payload: KekaWFHCreateRequest,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        End-to-End Write Flow for WFH Request:
        Resolves Keka employee UUID if user_id or internal ID passed.
        Submits request to Keka POST /time/wfh.
        """
        from app.modules.keka.leave_service import KekaMappingNotFoundError

        target_emp_id = payload.employeeId
        if user_id:
            mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
            if not mapping or not mapping.keka_employee_id:
                raise KekaMappingNotFoundError(user_id=user_id)
            target_emp_id = mapping.keka_employee_id.strip()

        clean_payload = payload.model_dump(exclude_unset=True)
        clean_payload["employeeId"] = target_emp_id
        res = await KekaClient.create_wfh_request(clean_payload)
        return {
            "success": True,
            "keka_employee_id": target_emp_id,
            "keka_response": res,
            "message": "WFH request submitted successfully in Keka.",
        }

    @staticmethod
    async def create_od_flow(
        db: AsyncSession,
        payload: KekaODCreateRequest,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        End-to-End Write Flow for On Duty Request:
        Resolves Keka employee UUID if user_id or internal ID passed.
        Submits request to Keka POST /time/od.
        """
        from app.modules.keka.leave_service import KekaMappingNotFoundError

        target_emp_id = payload.employeeId
        if user_id:
            mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
            if not mapping or not mapping.keka_employee_id:
                raise KekaMappingNotFoundError(user_id=user_id)
            target_emp_id = mapping.keka_employee_id.strip()

        clean_payload = payload.model_dump(exclude_unset=True)
        clean_payload["employeeId"] = target_emp_id
        res = await KekaClient.create_od_request(clean_payload)
        return {
            "success": True,
            "keka_employee_id": target_emp_id,
            "keka_response": res,
            "message": "On Duty request submitted successfully in Keka.",
        }


# Alias for backward-compatibility and clean service interface
KekaService = KekaEmployeeMappingService




