from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.modules.users.model import User


api_router = APIRouter()

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.roles.router import router as roles_router
from app.modules.holidays.router import router as holidays_router
from app.modules.leave_types.router import router as leave_types_router
from app.modules.leave_balances.router import router as leave_balances_router
from app.modules.dashboard.router import router as dashboard_router

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(roles_router, prefix="/roles", tags=["Roles"])
api_router.include_router(holidays_router, prefix="/holidays", tags=["Holidays"])
api_router.include_router(leave_types_router, prefix="/leave-types", tags=["Leave Types"])
api_router.include_router(leave_balances_router, prefix="/leave-balances", tags=["Leave Balances"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])

from app.modules.working_calendar.router import router as working_calendar_router
api_router.include_router(working_calendar_router, prefix="/working-calendar", tags=["Working Calendar"])

from app.modules.clients.router import router as clients_router
from app.modules.projects.router import router as projects_router
from app.modules.leave_requests.router import router as leave_requests_router
from app.modules.timesheets.router import router as timesheets_router
from app.modules.project_assignments.router import router as project_assignments_router
from app.modules.tools.router import router as tools_router
from app.modules.tool_allocations.router import router as tool_allocations_router
from app.modules.working_calendar.router import router as working_calendar_router
from app.modules.settings.router import router as settings_router

from app.modules.weekend_work.router import router as weekend_work_router
from app.modules.reports.router import router as reports_router
from app.modules.notifications.router import router as notifications_router
from app.modules.milestones.router import router as milestones_router

api_router.include_router(clients_router, prefix="/clients", tags=["Clients"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(project_assignments_router, prefix="/project-assignments", tags=["Project Assignments"])
api_router.include_router(leave_requests_router, prefix="/leave-requests", tags=["Leave Requests"])
api_router.include_router(timesheets_router, prefix="/timesheets", tags=["Timesheets"])
api_router.include_router(tools_router, prefix="/tools", tags=["Tools"])
api_router.include_router(tool_allocations_router, prefix="/tool-allocations", tags=["Tool Allocations"])
api_router.include_router(weekend_work_router, prefix="/weekend-work", tags=["Weekend Work Overtime"])
api_router.include_router(working_calendar_router, prefix="/working-calendar", tags=["Working Calendar"])
api_router.include_router(settings_router, prefix="/settings", tags=["System Settings"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports & Analytics"])
api_router.include_router(reports_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(milestones_router, prefix="/milestones", tags=["Milestones"])




@api_router.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint that verifies database connection."""
    try:
        result = await db.execute(text("SELECT 1"))
        db_status = "connected" if result.scalar() == 1 else "unknown"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    return {
        "status": "online",
        "database": db_status,
    }
