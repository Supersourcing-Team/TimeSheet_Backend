from typing import List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.project import Project
from app.models.project_assignment import ProjectAssignment
from app.models.timesheet import Timesheet
from app.models.client import Client


class AnalyticsRepository:
    """Repository for Analytics queries."""

    @staticmethod
    async def get_team_utilization(
        db: AsyncSession,
        pm_user_id: int = None,
        is_admin: bool = False,
    ) -> List[Tuple[User, float, float, float]]:
        # This groups timesheets by user and returns total, billable, non_billable hours
        # We need to consider all users, and for each user, their timesheets in the PM's projects.
        
        query = (
            select(
                User,
                func.sum(Timesheet.billable_hours + Timesheet.non_billable_hours).label('total_logged'),
                func.sum(Timesheet.billable_hours).label('total_billable'),
                func.sum(Timesheet.non_billable_hours).label('total_non_billable'),
            )
            .select_from(User)
            .outerjoin(ProjectAssignment, ProjectAssignment.user_id == User.id)
            .outerjoin(Project, Project.id == ProjectAssignment.project_id)
            .outerjoin(Timesheet, Timesheet.project_assignment_id == ProjectAssignment.id)
        )

        if not is_admin and pm_user_id:
            # Filter users that are assigned to projects managed by the PM
            # AND only sum timesheets for projects managed by the PM
            query = query.filter(Project.project_manager_id == pm_user_id)

        query = query.group_by(User.id)
        
        # Load user role for department/title mapping if needed
        query = query.options(selectinload(User.role))
        
        result = await db.execute(query)
        rows = result.all()
        
        # Format the result
        return [(row[0], row[1] or 0.0, row[2] or 0.0, row[3] or 0.0) for row in rows]

    @staticmethod
    async def get_pm_projects(
        db: AsyncSession,
        user_id: int,
        pm_user_id: int = None,
        is_admin: bool = False,
    ) -> List[Project]:
        # Get projects assigned to the user, managed by pm_user_id
        query = (
            select(Project)
            .join(ProjectAssignment)
            .filter(ProjectAssignment.user_id == user_id)
        )
        if not is_admin and pm_user_id:
            query = query.filter(Project.project_manager_id == pm_user_id)
            
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_project_financials(
        db: AsyncSession,
        pm_user_id: int = None,
        is_admin: bool = False,
    ) -> List[Tuple[Project, float]]:
        # Calculate spent budget per project based on billable hours * user's billing_rate
        # Assuming User has no billing rate in the schema, we'll use a fixed rate or project budget if applicable
        # Let's sum (billable_hours) for now and assume a fixed rate of $150/hr for financials, since there is no billing_rate field in User.
        
        query = (
            select(
                Project,
                func.sum(Timesheet.billable_hours).label('total_billable_hours')
            )
            .outerjoin(ProjectAssignment, ProjectAssignment.project_id == Project.id)
            .outerjoin(Timesheet, Timesheet.project_assignment_id == ProjectAssignment.id)
            .options(
                selectinload(Project.client),
                selectinload(Project.project_manager),
            )
        )
        
        if not is_admin and pm_user_id:
            query = query.filter(Project.project_manager_id == pm_user_id)
            
        query = query.group_by(Project.id)
        
        result = await db.execute(query)
        rows = result.all()
        
        # Return project and total billable hours (which we will convert to $ spent in service)
        return [(row[0], row[1] or 0.0) for row in rows]
