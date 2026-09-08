from datetime import date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
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
        # 1. Validate date is not in the future
        TimesheetValidator.validate_not_future_date(timesheet_in.timesheet_date)

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

        if entry.user_id != current_user.id:
            raise ForbiddenException(detail="You can only update your own timesheet entries.")

        update_data = timesheet_in.model_dump(exclude_unset=True)

        target_date = update_data.get("timesheet_date", entry.timesheet_date)
        target_assignment = update_data.get("project_assignment_id", entry.project_assignment_id)

        TimesheetValidator.validate_not_future_date(target_date)


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

        if entry.user_id != current_user.id:
            raise ForbiddenException(detail="You can only delete your own timesheet entries.")

        await TimesheetRepository.delete(db, entry)

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
