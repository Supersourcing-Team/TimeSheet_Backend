from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schema import LeaveReportSummary, TimesheetReportSummary


class ReportService:
    """Service generating aggregated report analytics and summaries."""

    @staticmethod
    async def generate_timesheet_report(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_id: Optional[int] = None,
        client_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_billable: Optional[bool] = None,
    ) -> TimesheetReportSummary:
        role_name = getattr(current_user.role, "name", None)

        # If Project_Manager, filter by projects managed by PM unless Admin/Account_Manager
        pm_filter_id = None
        if role_name == "Project_Manager":
            pm_filter_id = current_user.id

        items = await ReportRepository.get_timesheet_report_data(
            db,
            start_date=start_date,
            end_date=end_date,
            project_id=project_id,
            client_id=client_id,
            user_id=user_id,
            is_billable=is_billable,
            pm_user_id=pm_filter_id,
        )

        total_hours = sum((item.billable_hours + item.non_billable_hours) for item in items)
        billable_hours = sum(item.billable_hours for item in items)
        non_billable_hours = sum(item.non_billable_hours for item in items)


        return TimesheetReportSummary(
            start_date=start_date,
            end_date=end_date,
            total_hours=total_hours,
            billable_hours=billable_hours,
            non_billable_hours=non_billable_hours,
            total_entries=len(items),
            items=items,
        )

    @staticmethod
    async def generate_leave_report(
        db: AsyncSession,
        current_user: User,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
        leave_type_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> LeaveReportSummary:
        items = await ReportRepository.get_leave_report_data(
            db,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            leave_type_id=leave_type_id,
            status=status,
        )

        approved_count = sum(1 for item in items if item.status == "Approved")
        pending_count = sum(1 for item in items if item.status == "Pending")
        rejected_count = sum(1 for item in items if item.status == "Rejected")

        return LeaveReportSummary(
            start_date=start_date,
            end_date=end_date,
            total_requests=len(items),
            approved_requests=approved_count,
            pending_requests=pending_count,
            rejected_requests=rejected_count,
            items=items,
        )

    @staticmethod
    async def get_analytics_summary(db: AsyncSession):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.project import Project
        from app.modules.projects.service import ProjectService
        from app.modules.reports.schema import AnalyticsSummaryResponse

        from app.models.tool_allocation import ToolAllocation

        stmt = select(Project).options(
            selectinload(Project.client),
            selectinload(Project.project_manager),
            selectinload(Project.assignments),
            selectinload(Project.tool_allocations).selectinload(ToolAllocation.tool)
        ).where(Project.is_active == True)

        res = await db.execute(stmt)
        projects = list(res.scalars().all())

        financials = await ProjectService.compute_financials_for_projects(db, projects)

        total_budget = sum(p.budget for p in financials if p.budget)
        total_revenue = sum(p.revenue for p in financials)
        total_cost = sum(p.cost for p in financials)
        total_profit = sum(p.profit for p in financials)
        active_projects_count = sum(1 for p in projects if p.status.lower() in ["active", "planning"])

        return AnalyticsSummaryResponse(
            total_budget=round(total_budget, 2),
            total_revenue=round(total_revenue, 2),
            total_cost=round(total_cost, 2),
            total_profit=round(total_profit, 2),
            active_projects_count=active_projects_count,
        )

    @staticmethod
    async def generate_ledger_csv(db: AsyncSession) -> str:
        import csv
        import io
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.project import Project
        from app.modules.projects.service import ProjectService

        from app.models.tool_allocation import ToolAllocation

        stmt = select(Project).options(
            selectinload(Project.client),
            selectinload(Project.project_manager),
            selectinload(Project.assignments),
            selectinload(Project.tool_allocations).selectinload(ToolAllocation.tool)
        ).where(Project.is_active == True)
        res = await db.execute(stmt)
        projects = list(res.scalars().all())

        financials = await ProjectService.compute_financials_for_projects(db, projects)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Project ID",
            "Project Name",
            "Client Name",
            "Project Manager",
            "Status",
            "Budget (INR)",
            "Hours Logged",
            "Cost (INR)",
            "Revenue (INR)",
            "Profit (INR)",
        ])

        for p in financials:
            writer.writerow([
                p.id,
                p.project_name,
                p.client_name or "N/A",
                p.project_manager_name or "N/A",
                p.status.upper(),
                f"{p.budget:.2f}" if p.budget else "0.00",
                f"{p.logged_hours:.2f}",
                f"{p.cost:.2f}",
                f"{p.revenue:.2f}",
                f"{p.profit:.2f}",
            ])

        return output.getvalue()

    @staticmethod
    async def generate_pnl_pdf(db: AsyncSession) -> bytes:
        import io
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from app.models.project import Project
        from app.modules.projects.service import ProjectService
        from app.models.tool_allocation import ToolAllocation

        stmt = select(Project).options(
            selectinload(Project.client),
            selectinload(Project.project_manager),
            selectinload(Project.assignments),
            selectinload(Project.tool_allocations).selectinload(ToolAllocation.tool)
        ).where(Project.is_active == True)

        res = await db.execute(stmt)
        projects = list(res.scalars().all())

        financials = await ProjectService.compute_financials_for_projects(db, projects)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#2563EB'),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=18,
        )

        elements.append(Paragraph("SuperTime - Portfolio P&L Summary Report", title_style))
        elements.append(Paragraph("Timesheet & Resource Governance Financial Ledger", subtitle_style))

        total_budget = sum(p.budget for p in financials if p.budget)
        total_revenue = sum(p.revenue for p in financials)
        total_cost = sum(p.cost for p in financials)
        total_profit = sum(p.profit for p in financials)

        summary_data = [
            ["Total Client Contracts", "Total Revenue", "Total Internal Cost", "Net Portfolio Profit"],
            [f"Rs. {total_budget:,.2f}", f"Rs. {total_revenue:,.2f}", f"Rs. {total_cost:,.2f}", f"Rs. {total_profit:,.2f}"]
        ]
        summary_table = Table(summary_data, colWidths=[130, 130, 130, 150])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EFF6FF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1D4ED8')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, 1), 11),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#0F172A')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BFDBFE')),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        table_data = [["ID", "Project Name", "Client", "Hours", "Budget (INR)", "Cost (INR)", "Revenue (INR)", "Profit (INR)"]]
        for p in financials:
            table_data.append([
                str(p.id),
                p.project_name[:20],
                (p.client_name or "N/A")[:15],
                f"{p.logged_hours:.1f}",
                f"{p.budget:,.2f}" if p.budget else "0.00",
                f"{p.cost:,.2f}",
                f"{p.revenue:,.2f}",
                f"{p.profit:,.2f}",
            ])

        p_table = Table(table_data, colWidths=[30, 110, 85, 45, 80, 80, 80, 80])
        p_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(p_table)

        doc.build(elements)
        return buffer.getvalue()

