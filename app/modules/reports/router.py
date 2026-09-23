from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.permissions import require_roles
from app.modules.users.model import User
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
    summary="Get aggregated project financials",
)
@router.get(
    "/analytics",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated project financials",
)
@router.get(
    "/analytics/project-financials",
    response_model=dict,
    dependencies=[Depends(report_authorized_roles)],
    summary="Get aggregated project financials",
)
async def get_project_financials(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.projects.service import ProjectService
    service = ProjectService(db)
    projects = await service.get_all_projects(current_user=current_user)
    return success_response(
        data=[p.model_dump(mode="json") for p in projects],
        message="Project financials retrieved successfully",
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
    "/billing-ledger",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Client Billing Ledger (CSV)",
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
    "/portfolio-pnl",
    dependencies=[Depends(report_authorized_roles)],
    summary="Download Portfolio P&L Summary (PDF)",
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


pm_only = require_roles("Project_Manager")


@router.get(
    "/daily-eod/preview",
    response_model=dict,
    dependencies=[Depends(pm_only)],
    summary="Get preview of all employees' submitted EOD logs for a specific day",
)
async def get_daily_eod_preview(
    date_val: Optional[date] = Query(None, alias="date", description="Target EOD date (defaults to today)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.eod_report_service import EodReportService
    target_date = date_val or date.today()
    entries = await EodReportService.get_daily_eod_entries(db, target_date)
    total_b = sum(e["billable_hours"] for e in entries)
    total_nb = sum(e["non_billable_hours"] for e in entries)
    unique_employees = len(set(e["employee_id"] for e in entries))

    return success_response(
        data={
            "date": str(target_date),
            "total_submissions": len(entries),
            "total_employees": unique_employees,
            "total_billable_hours": round(total_b, 2),
            "total_non_billable_hours": round(total_nb, 2),
            "grand_total_hours": round(total_b + total_nb, 2),
            "entries": entries,
        },
        message="Daily EOD report preview retrieved successfully",
    )


@router.get(
    "/daily-eod/export",
    dependencies=[Depends(pm_only)],
    summary="Download consolidated daily EOD timesheet report for all employees (.xlsx or .csv)",
)
async def export_daily_eod(
    date_val: Optional[date] = Query(None, alias="date", description="Target EOD date (defaults to today)"),
    format_type: str = Query("xlsx", alias="format", description="Export format (xlsx or csv)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import Response
    from app.services.eod_report_service import EodReportService

    target_date = date_val or date.today()
    entries = await EodReportService.get_daily_eod_entries(db, target_date)

    if format_type.lower() == "csv":
        csv_content = EodReportService.generate_daily_eod_csv(entries, target_date)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=daily_eod_report_{target_date.strftime('%Y%m%d')}.csv"},
        )

    # Default to formatted Excel (.xlsx)
    xlsx_bytes = EodReportService.generate_daily_eod_excel(entries, target_date)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=daily_eod_report_{target_date.strftime('%Y%m%d')}.xlsx"},
    )


@router.post(
    "/daily-eod/slack-notify",
    response_model=dict,
    dependencies=[Depends(pm_only)],
    summary="Send daily EOD report and Excel file directly to configured Slack channel",
)
async def notify_slack_daily_eod(
    date_val: Optional[date] = Query(None, alias="date", description="Target EOD date (defaults to today)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.eod_report_service import EodReportService
    from fastapi import HTTPException

    target_date = date_val or date.today()
    result = await EodReportService.send_daily_eod_to_slack(db, target_date)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to send report to Slack"))

    return success_response(
        data=result,
        message=result.get("message", "Daily EOD report sent to Slack successfully"),
    )



