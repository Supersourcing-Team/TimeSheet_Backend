import logging
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leave_balances.model import LeaveBalance
from app.modules.leave_balances.repository import LeaveBalanceRepository
from app.modules.leave_balances.schema import LeaveBalanceCreate, LeaveBalanceResponse, LeaveBalanceUpdate
from app.modules.leave_types.repository import LeaveTypeRepository

logger = logging.getLogger(__name__)


class LeaveBalanceService:
    @staticmethod
    def _format_balance_response(
        b: LeaveBalance,
        leave_type_name: Optional[str] = None,
        source: str = "local",
        is_live: bool = False,
        sync_error: Optional[str] = None,
        keka_leave_type_id: Optional[str] = None,
    ) -> LeaveBalanceResponse:
        remaining = max(0.0, b.allocated_days - b.used_days)
        return LeaveBalanceResponse(
            id=b.id,
            user_id=b.user_id,
            leave_type_id=b.leave_type_id,
            leave_type_name=leave_type_name,
            year=b.year,
            allocated_days=b.allocated_days,
            used_days=b.used_days,
            remaining_days=remaining,
            updated_at=b.updated_at or datetime.now(),
            keka_leave_type_id=keka_leave_type_id,
            available_balance=remaining,
            annual_quota=b.allocated_days,
            accrued_days=b.allocated_days,
            source=source,
            is_live=is_live,
            sync_error=sync_error,
        )

    @staticmethod
    async def get_user_balances(
        db: AsyncSession, user_id: int, year: Optional[int] = None
    ) -> List[LeaveBalanceResponse]:
        target_year = year or datetime.now().year
        keka_sync_error: Optional[str] = None

        # 1. Check if user is mapped to Keka and integration is configured
        try:
            from app.services.keka.keka_auth import KekaAuthManager, KekaAuthError
            from app.services.keka.keka_client import KekaAPIError, KekaClient
            from app.modules.keka.repository import KekaEmployeeMappingRepository

            if KekaAuthManager.is_configured():
                mapping = await KekaEmployeeMappingRepository.get_by_local_user_id(db, user_id)
                if mapping and mapping.keka_employee_id:
                    keka_emp_id = mapping.keka_employee_id.strip()
                    try:
                        raw_result = await KekaClient.get_leave_balances(employee_ids=[keka_emp_id])
                        data_list = raw_result.get("data", []) if isinstance(raw_result, dict) else []
                        if isinstance(data_list, list) and data_list:
                            # Safely find the entry whose employeeId matches the requested keka_emp_id
                            emp_entry = next(
                                (
                                    e
                                    for e in data_list
                                    if str(e.get("employeeId") or "").strip().lower() == keka_emp_id.lower()
                                ),
                                None,
                            )
                            if not emp_entry:
                                logger.warning(
                                    "Keka leave balance response did not contain employeeId %s (found %s entries)",
                                    keka_emp_id,
                                    len(data_list),
                                )
                                keka_sync_error = (
                                    f"Employee '{keka_emp_id}' not found in Keka leave balance response"
                                )
                            else:
                                keka_balances = emp_entry.get("leaveBalance") or emp_entry.get("leaveBalances") or []
                                if isinstance(keka_balances, list) and keka_balances:
                                    # Authoritative live Keka leave balances
                                    active_leave_types = await LeaveTypeRepository.get_all(db, active_only=True)
                                    keka_id_to_lt = {
                                        lt.keka_leave_type_id: lt for lt in active_leave_types if lt.keka_leave_type_id
                                    }
                                    name_to_lt = {lt.name.lower().strip(): lt for lt in active_leave_types}

                                    keka_responses: List[LeaveBalanceResponse] = []
                                    for idx, kb in enumerate(keka_balances):
                                        keka_lt_id = str(kb.get("leaveTypeId") or "").strip()
                                        keka_lt_name = kb.get("leaveTypeName") or f"Leave Type {idx + 1}"

                                        # Prefer exact keka_leave_type_id match.
                                        # Use normalized-name fallback only when candidate local leave type is not already mapped to a different Keka leave-type ID.
                                        local_lt = keka_id_to_lt.get(keka_lt_id)
                                        if not local_lt:
                                            candidate = name_to_lt.get(keka_lt_name.lower().strip())
                                            if candidate and not candidate.keka_leave_type_id:
                                                local_lt = candidate

                                        local_lt_id = local_lt.id if local_lt else (1000 + idx)

                                        avail = float(
                                            kb.get("availableBalance")
                                            if kb.get("availableBalance") is not None
                                            else kb.get("available", 0.0) or 0.0
                                        )
                                        used = float(
                                            kb.get("used")
                                            if kb.get("used") is not None
                                            else kb.get("consumed", 0.0) or 0.0
                                        )
                                        quota = float(
                                            kb.get("annualQuota")
                                            if kb.get("annualQuota") is not None
                                            else kb.get("total", (avail + used)) or 0.0
                                        )
                                        accrued = float(
                                            kb.get("accrued")
                                            if kb.get("accrued") is not None
                                            else kb.get("accruedBalance", 0.0) or 0.0
                                        )

                                        keka_responses.append(
                                            LeaveBalanceResponse(
                                                id=local_lt_id,
                                                user_id=user_id,
                                                leave_type_id=local_lt_id,
                                                leave_type_name=local_lt.name if local_lt else keka_lt_name,
                                                year=target_year,
                                                allocated_days=quota,
                                                used_days=used,
                                                remaining_days=avail,
                                                updated_at=datetime.now(),
                                                keka_leave_type_id=keka_lt_id or None,
                                                available_balance=avail,
                                                annual_quota=quota,
                                                accrued_days=accrued,
                                                source="keka",
                                                is_live=True,
                                                sync_error=None,
                                            )
                                        )

                                    if keka_responses:
                                        logger.info(
                                            "Fetched %s live Keka leave balances for user %s (Keka ID: %s)",
                                            len(keka_responses),
                                            user_id,
                                            keka_emp_id,
                                        )
                                        return keka_responses
                    except (KekaAuthError, KekaAPIError) as api_err:
                        err_msg = str(api_err)
                        logger.warning(
                            "Failed to fetch live Keka leave balances for user %s (%s): %s",
                            user_id,
                            keka_emp_id,
                            err_msg,
                        )
                        keka_sync_error = f"Failed to fetch live Keka balances: {err_msg}"
                    except Exception as exc:
                        err_msg = str(exc)
                        logger.warning(
                            "Unexpected error fetching live Keka leave balances for user %s: %s",
                            user_id,
                            err_msg,
                        )
                        keka_sync_error = f"Keka balance query failed: {err_msg}"
        except Exception as check_err:
            logger.debug("Keka configuration check skipped: %s", check_err)

        # 2. Local fallback balances (clearly marked with source='local', is_live=False, and any sync_error)
        active_leave_types = await LeaveTypeRepository.get_all(db, active_only=True)
        custom_balances = await LeaveBalanceRepository.get_by_user_and_year(db, user_id, target_year)
        balance_map = {b.leave_type_id: b for b in custom_balances}

        responses = []
        for lt in active_leave_types:
            if lt.id in balance_map:
                b = balance_map[lt.id]
                responses.append(
                    LeaveBalanceService._format_balance_response(
                        b,
                        leave_type_name=lt.name,
                        source="local",
                        is_live=False,
                        sync_error=keka_sync_error,
                        keka_leave_type_id=getattr(lt, "keka_leave_type_id", None),
                    )
                )
            else:
                # Direct reference from Admin configured LeaveType policy (days_per_year)
                allocated = float(lt.days_per_year) if lt.days_per_year is not None else 0.0
                responses.append(
                    LeaveBalanceResponse(
                        id=lt.id,
                        user_id=user_id,
                        leave_type_id=lt.id,
                        leave_type_name=lt.name,
                        year=target_year,
                        allocated_days=allocated,
                        used_days=0.0,
                        remaining_days=allocated,
                        updated_at=datetime.now(),
                        keka_leave_type_id=getattr(lt, "keka_leave_type_id", None),
                        available_balance=allocated,
                        annual_quota=allocated,
                        accrued_days=allocated,
                        source="local",
                        is_live=False,
                        sync_error=keka_sync_error,
                    )
                )

        return responses


    @staticmethod
    async def allocate_balance(
        db: AsyncSession, data: LeaveBalanceCreate
    ) -> LeaveBalanceResponse:
        leave_type = await LeaveTypeRepository.get_by_id(db, data.leave_type_id)
        if not leave_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave type with ID {data.leave_type_id} not found",
            )
        existing = await LeaveBalanceRepository.get_specific_balance(
            db, user_id=data.user_id, leave_type_id=data.leave_type_id, year=data.year
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave balance allocation already exists for user {data.user_id}, leave type {data.leave_type_id}, year {data.year}",
            )
        balance = await LeaveBalanceRepository.create(
            db,
            user_id=data.user_id,
            leave_type_id=data.leave_type_id,
            year=data.year,
            allocated_days=data.allocated_days,
        )
        return LeaveBalanceService._format_balance_response(balance)

    @staticmethod
    async def update_balance(
        db: AsyncSession, balance_id: int, data: LeaveBalanceUpdate
    ) -> LeaveBalanceResponse:
        balance = await LeaveBalanceRepository.get_by_id(db, balance_id)
        if not balance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave balance with ID {balance_id} not found",
            )
        updated = await LeaveBalanceRepository.update(db, balance, **data.model_dump(exclude_unset=True))
        return LeaveBalanceService._format_balance_response(updated)
