from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User
from app.modules.reports.schema import LeaveReportSummary, TimesheetReportSummary
from app.modules.reports.service import ReportService

router = APIRouter()
report_authorized_roles = require_roles("Admin", "Account_Manager", "Project_Manager")


@router.get(
    "/timesheets",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated timesheet analytics report",
)
async def get_timesheet_report(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    is_billable: Optional[bool] = Query(None, description="Filter by billable status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    report = await ReportService.generate_timesheet_report(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        project_id=project_id,
        client_id=client_id,
        user_id=user_id,
        is_billable=is_billable,
    )
    return success_response(
        data=report.model_dump(mode="json"),
        message="Timesheet report generated successfully",
    )


@router.get(
    "/leaves",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated leave analytics report",
)
async def get_leave_report(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    leave_type_id: Optional[int] = Query(None, description="Filter by leave type ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (Pending/Approved/Rejected)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    report = await ReportService.generate_leave_report(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        leave_type_id=leave_type_id,
        status=status_filter,
    )
    return success_response(
        data=report.model_dump(mode="json"),
        message="Leave analytics report generated successfully",
    )


@router.get(
    "/project-financials",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated project financials analytics",
)
@router.get(
    "/analytics",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated portfolio analytics (Total Budget, Revenue, Cost, Profit)",
)
@router.get(
    "/analytics/project-financials",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated project financials analytics",
)
@router.get(
    "/summary",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated portfolio analytics summary",
)


async def get_analytics_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await ReportService.get_analytics_summary(db)
    return success_response(
        data=summary.model_dump(mode="json"),
        message="Analytics summary generated successfully",
    )


@router.get(
    "/export/ledger-csv",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Client Billing Ledger (CSV)",
)
@router.get(
    "/csv",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Client Billing Ledger (CSV)",
)
async def export_ledger_csv(
    db: AsyncSession = Depends(get_db),
):
    from fastapi import Response
    csv_content = await ReportService.generate_ledger_csv(db)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=client_billing_ledger.csv"},
    )


@router.get(
    "/export/pnl-pdf",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Portfolio P&L Summary (PDF)",
)
@router.get(
    "/pdf",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Portfolio P&L Summary (PDF)",
)
async def export_pnl_pdf(
    db: AsyncSession = Depends(get_db),
):
    from fastapi import Response
    pdf_bytes = await ReportService.generate_pnl_pdf(db)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=portfolio_pnl_summary.pdf"},
    )

