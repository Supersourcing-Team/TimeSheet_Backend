from datetime import date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.modules.timesheets.model import Timesheet
from app.modules.users.model import User
from app.modules.timesheets.repository import TimesheetRepository
from app.modules.timesheets.schema import (
    DailyTimesheetBreakdown,
    TimesheetCreate,
    TimesheetResponse,
    TimesheetUpdate,
    WeeklyTimesheetSummary,
)
from app.modules.timesheets.validator import TimesheetValidator


class TimesheetService:
    """Service handling business logic for Timesheets."""

    @staticmethod
    async def create_timesheet(
        db: AsyncSession,
        current_user: User,
        timesheet_in: TimesheetCreate,
    ) -> Timesheet:
        # 1. Validate date is not in the future, not a weekend, and not a holiday
        TimesheetValidator.validate_not_future_date(timesheet_in.timesheet_date)
        await TimesheetValidator.validate_not_weekend(
            db, current_user.id, timesheet_in.project_assignment_id, timesheet_in.timesheet_date
        )
        await TimesheetValidator.validate_not_holiday(db, timesheet_in.timesheet_date)

        # 2. Validate project assignment
        await TimesheetValidator.validate_project_assignment(
            db, current_user.id, timesheet_in.project_assignment_id
        )

        existing = await TimesheetRepository.get_by_user_project_date(
            db, current_user.id, timesheet_in.project_assignment_id, timesheet_in.timesheet_date
        )

        # 3. Validate max 24h/day limit (excluding existing if upsert)
        target_total_hours = timesheet_in.billable_hours + timesheet_in.non_billable_hours
        await TimesheetValidator.validate_daily_hours(
            db, 
            current_user.id, 
            timesheet_in.timesheet_date, 
            target_total_hours,
            exclude_id=existing.id if existing else None
        )

        # 4. Validate no leave conflict for this date
        await TimesheetValidator.validate_no_leave_conflict(
            db,
            current_user.id,
            timesheet_in.timesheet_date,
            target_total_hours,
        )

        if existing:
            # Upsert: Update completely the existing row
            update_data = {
                "billable_hours": timesheet_in.billable_hours,
                "billable_work_summary": timesheet_in.billable_work_summary,
                "non_billable_hours": timesheet_in.non_billable_hours,
                "non_billable_work_summary": timesheet_in.non_billable_work_summary,
            }
            return await TimesheetRepository.update(db, existing, update_data)

        # 4. Create timesheet entry
        timesheet = Timesheet(
            user_id=current_user.id,
            project_assignment_id=timesheet_in.project_assignment_id,
            timesheet_date=timesheet_in.timesheet_date,
            billable_hours=timesheet_in.billable_hours,
            billable_work_summary=timesheet_in.billable_work_summary,
            non_billable_hours=timesheet_in.non_billable_hours,
            non_billable_work_summary=timesheet_in.non_billable_work_summary,
        )
        return await TimesheetRepository.create(db, timesheet)

    @staticmethod
    async def create_timesheets_batch(
        db: AsyncSession,
        current_user: User,
        batch_in: List[TimesheetCreate],
    ) -> List[Timesheet]:
        """
        Atomically process and persist a batch of timesheet entries.
        Uses a nested savepoint / transaction block: if any row fails validation or persistence,
        all partial database writes are rolled back.
        """
        if not batch_in:
            return []

        # Validate duplicate combinations within the batch itself
        seen_keys = set()
        for item in batch_in:
            key = (item.project_assignment_id, item.timesheet_date)
            if key in seen_keys:
                raise BadRequestException(
                    detail=f"Duplicate entry in batch for assignment {item.project_assignment_id} on {item.timesheet_date}."
                )
            seen_keys.add(key)

        created_or_updated: List[Timesheet] = []
        try:
            async with db.begin_nested():
                for item in batch_in:
                    # Validate date
                    TimesheetValidator.validate_not_future_date(item.timesheet_date)
                    await TimesheetValidator.validate_not_weekend(
                        db, current_user.id, item.project_assignment_id, item.timesheet_date
                    )
                    await TimesheetValidator.validate_not_holiday(db, item.timesheet_date)
                    await TimesheetValidator.validate_project_assignment(
                        db, current_user.id, item.project_assignment_id
                    )

                    existing = await TimesheetRepository.get_by_user_project_date(
                        db, current_user.id, item.project_assignment_id, item.timesheet_date
                    )

                    target_total_hours = item.billable_hours + item.non_billable_hours
                    await TimesheetValidator.validate_daily_hours(
                        db,
                        current_user.id,
                        item.timesheet_date,
                        target_total_hours,
                        exclude_id=existing.id if existing else None,
                    )
                    await TimesheetValidator.validate_no_leave_conflict(
                        db,
                        current_user.id,
                        item.timesheet_date,
                        target_total_hours,
                    )

                    if existing:
                        update_data = {
                            "billable_hours": item.billable_hours,
                            "billable_work_summary": item.billable_work_summary,
                            "non_billable_hours": item.non_billable_hours,
                            "non_billable_work_summary": item.non_billable_work_summary,
                        }
                        for field, value in update_data.items():
                            if value is not None:
                                setattr(existing, field, value)
                        db.add(existing)
                        created_or_updated.append(existing)
                    else:
                        ts = Timesheet(
                            user_id=current_user.id,
                            project_assignment_id=item.project_assignment_id,
                            timesheet_date=item.timesheet_date,
                            billable_hours=item.billable_hours,
                            billable_work_summary=item.billable_work_summary,
                            non_billable_hours=item.non_billable_hours,
                            non_billable_work_summary=item.non_billable_work_summary,
                        )
                        db.add(ts)
                        created_or_updated.append(ts)

                await db.flush()
            await db.commit()
            for obj in created_or_updated:
                await db.refresh(obj)
            return created_or_updated
        except Exception:
            await db.rollback()
            raise


    @staticmethod
    async def get_my_timesheets(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_assignment_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Timesheet], int]:
        return await TimesheetRepository.list_by_user(
            db,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            project_assignment_id=project_assignment_id,
            page=page,
        )

    @staticmethod
    async def get_managed_timesheets(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_assignment_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Timesheet], int]:
        return await TimesheetRepository.list_managed_by_pm(
            db,
            pm_user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            project_assignment_id=project_assignment_id,
            page=page,
            limit=limit,
        )

    @staticmethod
    async def get_timesheet_by_id(
        db: AsyncSession,
        timesheet_id: int,
        current_user: User,
    ) -> Timesheet:
        entry = await TimesheetRepository.get_by_id(db, timesheet_id)
        if not entry:
            raise NotFoundException(detail="Timesheet entry not found.")

        role_name = getattr(current_user.role, "name", None)
        # Admins and Project Managers can view any timesheet entry (PMs need
        # this to look up entries returned after creation). Ownership check
        # below still protects against cross-user access for all other roles.
        is_privileged = role_name in ("Admin", "Project_Manager")
        if entry.user_id != current_user.id and not is_privileged:
            raise ForbiddenException(detail="You do not have permission to view this timesheet entry.")

        return entry

    @staticmethod
    async def update_timesheet(
        db: AsyncSession,
        timesheet_id: int,
        current_user: User,
        timesheet_in: TimesheetUpdate,
    ) -> Timesheet:
        entry = await TimesheetRepository.get_by_id(db, timesheet_id)
        if not entry:
            raise NotFoundException(detail="Timesheet entry not found.")

        role_name = getattr(current_user.role, "name", None) or getattr(current_user, "role", "")
        is_admin = role_name in ("Admin", "admin")

        if entry.user_id != current_user.id and not is_admin:
            raise ForbiddenException(detail="You can only update your own timesheet entries.")

        if entry.status == "approved" and not is_admin:
            raise BadRequestException(detail="Approved timesheet entries cannot be modified.")

        update_data = timesheet_in.model_dump(exclude_unset=True)

        target_date = update_data.get("timesheet_date", entry.timesheet_date)
        target_assignment = update_data.get("project_assignment_id", entry.project_assignment_id)

        TimesheetValidator.validate_not_future_date(target_date)
        if "timesheet_date" in update_data or "project_assignment_id" in update_data:
            await TimesheetValidator.validate_not_weekend(
                db, current_user.id, target_assignment, target_date
            )
        if "timesheet_date" in update_data:
            await TimesheetValidator.validate_not_holiday(db, target_date)


        if "project_assignment_id" in update_data:
            await TimesheetValidator.validate_project_assignment(
                db, current_user.id, target_assignment
            )

        if any(k in update_data for k in ["billable_hours", "non_billable_hours", "timesheet_date"]):
            b_hours = update_data.get("billable_hours", entry.billable_hours)
            nb_hours = update_data.get("non_billable_hours", entry.non_billable_hours)
            target_hours = b_hours + nb_hours
            await TimesheetValidator.validate_daily_hours(
                db,
                user_id=current_user.id,
                timesheet_date=target_date,
                new_hours=target_hours,
                exclude_id=entry.id,
            )
            # Validate no leave conflict
            await TimesheetValidator.validate_no_leave_conflict(
                db,
                user_id=current_user.id,
                timesheet_date=target_date,
                new_hours=target_hours,
            )

        return await TimesheetRepository.update(db, entry, update_data)

    @staticmethod
    async def delete_timesheet(
        db: AsyncSession,
        timesheet_id: int,
        current_user: User,
    ) -> None:
        entry = await TimesheetRepository.get_by_id(db, timesheet_id)
        if not entry:
            raise NotFoundException(detail="Timesheet entry not found.")

        role_name = getattr(current_user.role, "name", None) or getattr(current_user, "role", "")
        is_admin = role_name in ("Admin", "admin")

        if entry.user_id != current_user.id and not is_admin:
            raise ForbiddenException(detail="You can only delete your own timesheet entries.")

        if entry.status == "approved" and not is_admin:
            raise BadRequestException(detail="Approved timesheet entries cannot be deleted.")

        await TimesheetRepository.delete(db, entry)

    @staticmethod
    async def approve_timesheet(
        db: AsyncSession,
        timesheet_id: int,
        reviewer_user: User,
    ) -> Timesheet:
        entry = await TimesheetRepository.get_by_id(db, timesheet_id)
        if not entry:
            raise NotFoundException(detail="Timesheet entry not found.")

        # Check authorization: Admin or assigned PM for the timesheet's project
        role_name = getattr(reviewer_user.role, "name", None) or getattr(reviewer_user, "role", "")
        is_admin = role_name in ("Admin", "admin")

        project_pm_id = None
        if entry.project_assignment and getattr(entry.project_assignment, "project", None):
            project_pm_id = getattr(entry.project_assignment.project, "project_manager_id", None)

        if not is_admin and project_pm_id != reviewer_user.id:
            raise ForbiddenException(
                detail="Only the Project Manager assigned to this project or an Admin can approve this timesheet."
            )

        if entry.status not in ("submitted", "pending"):
            raise ConflictException(
                detail=f"Cannot approve timesheet with status '{entry.status}'."
            )

        return await TimesheetRepository.update(db, entry, {"status": "approved"})

    @staticmethod
    async def reject_timesheet(
        db: AsyncSession,
        timesheet_id: int,
        reviewer_user: User,
    ) -> Timesheet:
        entry = await TimesheetRepository.get_by_id(db, timesheet_id)
        if not entry:
            raise NotFoundException(detail="Timesheet entry not found.")

        # Check authorization: Admin or assigned PM for the timesheet's project
        role_name = getattr(reviewer_user.role, "name", None) or getattr(reviewer_user, "role", "")
        is_admin = role_name in ("Admin", "admin")

        project_pm_id = None
        if entry.project_assignment and getattr(entry.project_assignment, "project", None):
            project_pm_id = getattr(entry.project_assignment.project, "project_manager_id", None)

        if not is_admin and project_pm_id != reviewer_user.id:
            raise ForbiddenException(
                detail="Only the Project Manager assigned to this project or an Admin can reject this timesheet."
            )

        if entry.status not in ("submitted", "pending"):
            raise ConflictException(
                detail=f"Cannot reject timesheet with status '{entry.status}'."
            )

        return await TimesheetRepository.update(db, entry, {"status": "rejected"})

    @staticmethod
    async def get_weekly_summary(
        db: AsyncSession,
        current_user: User,
        target_date: Optional[date] = None,
    ) -> WeeklyTimesheetSummary:
        ref_date = target_date or date.today()
        # Find Monday of target week
        monday = ref_date - timedelta(days=ref_date.weekday())
        sunday = monday + timedelta(days=6)

        entries = await TimesheetRepository.get_entries_in_range(
            db, user_id=current_user.id, start_date=monday, end_date=sunday
        )

        # Map entries by date
        entries_by_date = {}
        total_weekly_hours = 0.0
        for entry in entries:
            d = entry.timesheet_date
            if d not in entries_by_date:
                entries_by_date[d] = []
            entries_by_date[d].append(entry)
            total_weekly_hours += (entry.billable_hours + entry.non_billable_hours)

        daily_breakdowns = []
        for i in range(7):
            curr_d = monday + timedelta(days=i)
            day_entries = entries_by_date.get(curr_d, [])
            day_total = sum((e.billable_hours + e.non_billable_hours) for e in day_entries)
            resp_entries = [TimesheetResponse.model_validate(e) for e in day_entries]
            daily_breakdowns.append(
                DailyTimesheetBreakdown(
                    date=curr_d,
                    total_hours=day_total,
                    entries=resp_entries,
                )
            )

        return WeeklyTimesheetSummary(
            start_date=monday,
            end_date=sunday,
            total_weekly_hours=total_weekly_hours,
            daily_breakdowns=daily_breakdowns,
        )
