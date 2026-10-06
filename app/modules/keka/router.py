import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.permissions import require_admin
from app.modules.keka.schema import (
    KekaAllEmployeesResponse,
    KekaAttendanceTimeEntryCreate,
    KekaEmployeeCreateRequest,
    KekaEmployeeExitRequest,
    KekaEmployeeMappingCreate,
    KekaEmployeeMappingDeleteResponse,
    KekaEmployeeMappingResponse,
    KekaJobDetailsUpdateRequest,
    KekaMappingPreviewResponse,
    KekaODCreateRequest,
    KekaPaginatedEmployeesResponse,
    KekaWFHCreateRequest,
)
from app.modules.keka.service import KekaEmployeeMappingService, KekaService
from app.modules.keka.leave_service import KekaLeaveService
from app.modules.keka.attendance_service import KekaAttendanceService
from app.modules.users.model import User
from app.services.keka.keka_auth import KekaAuthError, KekaAuthManager
from app.services.keka.keka_client import KekaAPIError, KekaClient

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status",
    summary="Get Keka integration configuration status",
    description="Returns whether Keka credentials are configured and current environment settings.",
)
async def get_keka_status(
    current_user: User = Depends(require_admin),
):
    creds = KekaAuthManager.get_credentials()
    is_configured = KekaAuthManager.is_configured()
    token_url = KekaAuthManager.get_token_url()

    masked_info = {
        "is_configured": is_configured,
        "company_name": creds["company_name"] or None,
        "environment": "sandbox" if "kekademo" in token_url else "production",
        "token_endpoint": token_url,
        "has_client_id": bool(creds["client_id"]),
        "has_client_secret": bool(creds["client_secret"]),
        "has_api_key": bool(creds["api_key"]),
        "is_token_cached": KekaAuthManager._access_token is not None,
    }

    return success_response(
        data=masked_info,
        message="Keka integration status retrieved successfully",
    )


@router.get(
    "/test-connection",
    summary="Test Keka API connection",
    description="Authenticates with Keka OAuth2 and fetches a small sample of employees to verify connectivity.",
)
async def test_keka_connection(
    current_user: User = Depends(require_admin),
):
    result = await KekaClient.test_connection()
    status_msg = "Keka connection test successful" if result.get("status") == "connected" else "Keka connection test failed"
    return success_response(
        data=result,
        message=status_msg,
    )


@router.post(
    "/clear-token-cache",
    summary="Clear Keka access token cache",
    description="Clears in-memory cached OAuth2 access token to force re-authentication on the next request.",
)
async def clear_token_cache(
    current_user: User = Depends(require_admin),
):
    KekaAuthManager.clear_cache()
    return success_response(
        data={"cleared": True},
        message="Keka access token cache cleared successfully",
    )


@router.get(
    "/employees",
    summary="Get paginated employees from Keka",
    description="Read-only endpoint that retrieves a single page of employee records from Keka HR API.",
)
async def get_keka_employees(
    pageNumber: int = Query(1, ge=1, description="Page number to retrieve (starts at 1)"),
    pageSize: int = Query(100, ge=1, le=200, description="Number of records per page (max 200)"),
    current_user: User = Depends(require_admin),
):
    try:
        raw_result = await KekaClient.get_employees(page_number=pageNumber, page_size=pageSize)
        validated = KekaPaginatedEmployeesResponse.model_validate(raw_result)
        return success_response(
            data=validated.model_dump(),
            message="Keka employees retrieved successfully",
        )
    except KekaAuthError as err:
        logger.error("Keka auth error on GET /employees: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    except KekaAPIError as err:
        logger.error("Keka API error on GET /employees: %s", err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error fetching Keka employees: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching employees from Keka.",
        )


@router.get(
    "/employees/all",
    summary="Get all employees from Keka across all pages",
    description="Read-only endpoint that automatically paginates through Keka HR API to return all employee records.",
)
async def get_all_keka_employees(
    current_user: User = Depends(require_admin),
):
    try:
        raw_result = await KekaClient.get_all_employees()
        validated = KekaAllEmployeesResponse.model_validate(raw_result)
        return success_response(
            data=validated.model_dump(),
            message="All Keka employees retrieved successfully",
        )
    except KekaAuthError as err:
        logger.error("Keka auth error on GET /employees/all: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    except KekaAPIError as err:
        logger.error("Keka API error on GET /employees/all: %s", err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error fetching all Keka employees: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching all employees from Keka.",
        )


@router.get(
    "/employees/mapping-preview",
    summary="Preview Keka employee to local user mappings",
    description="Purely read-only diagnostic endpoint that compares Keka employees with local users and classifies them into mapped, local_match, unmapped, or conflict. Does NOT mutate the database.",
)
async def get_keka_employee_mapping_preview(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        preview_data = await KekaEmployeeMappingService.get_mapping_preview(db)
        validated = KekaMappingPreviewResponse.model_validate(preview_data)
        return success_response(
            data=validated.model_dump(mode="json"),
            message="Keka employee mapping preview generated successfully",
        )
    except KekaAuthError as err:
        logger.error("Keka auth error on GET /employees/mapping-preview: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    except KekaAPIError as err:
        logger.error("Keka API error on GET /employees/mapping-preview: %s", err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error generating Keka mapping preview: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating employee mapping preview.",
        )


@router.get(
    "/mappings/employees",
    summary="List existing Keka employee mappings",
    description="Admin-only read-only endpoint that lists recorded 1:1 mappings between Keka employee UUIDs and local users.",
)
async def list_keka_employee_mappings(
    skip: int = Query(0, ge=0, description="Offset records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mappings, total = await KekaEmployeeMappingService.list_mappings(db, skip=skip, limit=limit)
    serialized = [KekaEmployeeMappingResponse.model_validate(m).model_dump(mode="json") for m in mappings]
    return success_response(
        data={"total": total, "items": serialized},
        message="Keka employee mappings retrieved successfully",
    )


@router.get(
    "/mappings/employees/{keka_employee_id}",
    summary="Get single Keka employee mapping by Keka employee UUID",
    description="Admin-only read-only endpoint that returns an existing employee mapping for the given Keka employee UUID.",
)
async def get_keka_employee_mapping(
    keka_employee_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mapping = await KekaEmployeeMappingService.get_by_keka_employee_id(db, keka_employee_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No mapping found for Keka employee ID '{keka_employee_id}'.",
        )

    validated = KekaEmployeeMappingResponse.model_validate(mapping)
    return success_response(
        data=validated.model_dump(mode="json"),
        message="Keka employee mapping retrieved successfully",
    )


@router.post(
    "/mappings/employees",
    summary="Create or update Keka employee to local user mapping",
    description="Admin-only endpoint to persist a 1:1 mapping between a Keka employee UUID and a local user.",
)
async def create_or_update_keka_employee_mapping(
    payload: KekaEmployeeMappingCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mapping = await KekaEmployeeMappingService.save_mapping(
        db,
        keka_employee_id=payload.keka_employee_id,
        local_user_id=payload.local_user_id,
        keka_employee_number=payload.keka_employee_number,
    )
    validated = KekaEmployeeMappingResponse.model_validate(mapping)
    return success_response(
        data=validated.model_dump(mode="json"),
        message="Keka employee mapping saved successfully",
    )


@router.delete(
    "/mappings/employees/{keka_employee_id}",
    summary="Delete Keka employee mapping",
    description="Admin-only endpoint to remove an existing mapping by Keka employee UUID.",
)
async def delete_keka_employee_mapping(
    keka_employee_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await KekaEmployeeMappingService.delete_mapping(db, keka_employee_id)
    response_data = {
        "keka_employee_id": keka_employee_id,
        "deleted": True,
        "message": f"Mapping for Keka employee '{keka_employee_id}' deleted successfully.",
    }
    validated = KekaEmployeeMappingDeleteResponse.model_validate(response_data)
    return success_response(
        data=validated.model_dump(mode="json"),
        message="Keka employee mapping deleted successfully",
    )


@router.post(
    "/mappings/auto-sync",
    summary="Auto-map all matched Keka employees to local users",
    description="Admin-only endpoint that automatically establishes 1:1 mappings for all candidates detected with clean matches.",
)
async def auto_sync_keka_mappings(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await KekaEmployeeMappingService.auto_sync_matched(db)
    return success_response(
        data=result,
        message=f"Auto-sync completed: {result.get('mapped_count', 0)} employees mapped.",
    )


@router.get(
    "/leave-types",
    summary="Get Keka configured leave types",
    description="Admin-only endpoint that fetches leave types directly from Keka HR API for configuration and mapping.",
)
async def get_keka_leave_types(
    current_user: User = Depends(require_admin),
):
    try:
        types = await KekaEmployeeMappingService.get_keka_leave_types()
        return success_response(
            data=types,
            message="Keka leave types retrieved successfully",
        )
    except KekaAuthError as err:
        logger.error("Keka auth error on GET /leave-types: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    except KekaAPIError as err:
        logger.error("Keka API error on GET /leave-types: %s", err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error fetching Keka leave types: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching leave types from Keka.",
        )


@router.get(
    "/leave-requests/{local_leave_id}/sync-status",
    summary="Get Keka synchronization status for a local leave request",
    description="Admin-only read-only endpoint that returns whether a local leave request has been pushed to Keka.",
)
async def get_keka_leave_sync_status(
    local_leave_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.keka.schema import KekaLeaveSyncStatusResponse
    from app.modules.leave_requests.repository import LeaveRequestRepository

    leave = await LeaveRequestRepository.get_by_id(db, local_leave_id)
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local leave request with ID {local_leave_id} not found.",
        )

    response_data = {
        "local_leave_id": leave.id,
        "user_id": leave.user_id,
        "synced_to_keka": bool(leave.synced_to_keka),
        "keka_leave_request_id": leave.keka_leave_request_id,
        "last_synced_at": leave.last_synced_at,
        "last_sync_error": leave.last_sync_error,
    }
    validated = KekaLeaveSyncStatusResponse.model_validate(response_data)
    return success_response(
        data=validated.model_dump(mode="json"),
        message="Keka leave sync status retrieved successfully",
    )


@router.post(
    "/leave-requests/{local_leave_id}/sync",
    summary="Manually trigger push of a local leave request to Keka",
    description="Admin-only action endpoint that pushes a specific local leave request to Keka via POST /time/leaverequests.",
)
async def sync_local_leave_to_keka(
    local_leave_id: int,
    keka_leave_type_id: Optional[str] = Query(None, description="Optional Keka leave type UUID override"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.keka.leave_service import KekaLeaveService
    from app.modules.keka.schema import KekaLeaveSyncActionResponse
    from app.modules.leave_requests.repository import LeaveRequestRepository

    leave = await LeaveRequestRepository.get_by_id(db, local_leave_id)
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local leave request with ID {local_leave_id} not found.",
        )

    result = await KekaLeaveService.sync_leave_to_keka(
        db, leave, keka_leave_type_id=keka_leave_type_id
    )
    validated = KekaLeaveSyncActionResponse.model_validate(result)
    status_msg = "Leave successfully pushed to Keka" if result.get("synced") else "Leave push to Keka failed"
    return success_response(
        data=validated.model_dump(mode="json"),
        message=status_msg,
    )


@router.get(
    "/attendance",
    summary="Get attendance records from Keka mapped to local users",
    description="Admin-only read-only endpoint that pulls attendance from Keka API across specified date range (up to 90 days per batch) and aligns with local employee mappings.",
)
async def get_keka_attendance(
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    employee_id: Optional[str] = Query(None, description="Optional Keka Employee UUID"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.modules.keka.attendance_service import KekaAttendanceService

    try:
        records = await KekaAttendanceService.get_attendance_records(
            db=db,
            from_date=from_date,
            to_date=to_date,
            employee_id=employee_id,
        )
        return success_response(
            data=records,
            message="Keka attendance records retrieved successfully",
        )
    except KekaAuthError as err:
        logger.error("Keka auth error on GET /attendance: %s", err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    except KekaAPIError as err:
        logger.error("Keka API error on GET /attendance: %s", err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error fetching attendance from Keka: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching attendance from Keka: {str(err)}",
        )


@router.get(
    "/attendance/exceptions",
    summary="Get attendance exceptions and absent-without-leave signals",
    description="Admin-only diagnostic endpoint that identifies missing punch-outs and absences without registered local leave for a date.",
)
async def get_keka_attendance_exceptions(
    target_date: Optional[str] = Query(None, alias="date", description="Date to check (YYYY-MM-DD), defaults to today"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date
    from app.modules.keka.attendance_service import KekaAttendanceService

    check_date = target_date or date.today().isoformat()
    try:
        exceptions = await KekaAttendanceService.get_attendance_exceptions(
            db=db,
            check_date=check_date,
        )
        return success_response(
            data=exceptions,
            message=f"Attendance exceptions for {check_date} retrieved successfully",
        )
    except Exception as err:
        logger.exception("Error checking attendance exceptions: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating attendance exceptions: {str(err)}",
        )


def _handle_keka_exception(err: Exception, action_description: str):
    """Centralized exception handling for Keka API operations."""
    if isinstance(err, HTTPException):
        raise err
    if isinstance(err, KekaAuthError):
        logger.error("Keka authentication error during %s: %s", action_description, err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate with Keka HR API. Please verify Keka credentials.",
        )
    if isinstance(err, KekaAPIError):
        logger.error("Keka API error during %s: %s", action_description, err)
        raise HTTPException(
            status_code=err.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        )
    logger.exception("Unexpected error during %s: %s", action_description, err)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"An error occurred while {action_description}.",
    )


# =============================================================================
# CATEGORY 1 – HR CORE & EMPLOYEE LIFECYCLE ENDPOINTS
# =============================================================================


@router.get(
    "/employees/update-fields",
    summary="Get employee update fields from Keka",
    description="Admin-only endpoint that retrieves supported employee update fields from Keka HR API.",
)
@router.get(
    "/employees/updatefields",
    summary="Get employee update fields from Keka (alias)",
    description="Admin-only endpoint that retrieves supported employee update fields from Keka HR API.",
)
async def get_keka_employee_update_fields(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_employee_update_fields()
        return success_response(data=data, message="Employee update fields retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching employee update fields")


@router.get(
    "/employees/{employee_id}",
    summary="Get single employee details from Keka",
    description="Admin-only endpoint that fetches full profile details for a given Keka employee UUID.",
)
async def get_keka_employee_details(
    employee_id: str,
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_employee(employee_id)
        return success_response(data=data, message="Employee details retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, f"fetching details for employee {employee_id}")


@router.post(
    "/employees",
    summary="Create a new employee in Keka",
    description="Admin-only endpoint that provisions a new employee in Keka HR via POST /hris/employees and links local user mapping.",
)
async def create_keka_employee(
    payload: KekaEmployeeCreateRequest,
    create_local_user: bool = Query(True, description="Create or link local user record"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaEmployeeMappingService.create_employee_flow(
            db=db, payload=payload, create_local_user=create_local_user
        )
        return success_response(data=data, message="Employee created successfully in Keka and synchronized to local database")
    except Exception as err:
        _handle_keka_exception(err, "creating employee in Keka")



@router.get(
    "/departments",
    summary="Get departments from Keka",
    description="Admin-only endpoint that retrieves company departments from Keka HR API.",
)
async def get_keka_departments(
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_departments(page_number=pageNumber, page_size=pageSize)
        return success_response(data=data, message="Departments retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching departments")


@router.get(
    "/job-titles",
    summary="Get job titles from Keka",
    description="Admin-only endpoint that retrieves job titles from Keka HR API.",
)
async def get_keka_job_titles(
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_job_titles(page_number=pageNumber, page_size=pageSize)
        return success_response(data=data, message="Job titles retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching job titles")


@router.get(
    "/locations",
    summary="Get locations from Keka",
    description="Admin-only endpoint that retrieves company office locations from Keka HR API.",
)
async def get_keka_locations(
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_locations(page_number=pageNumber, page_size=pageSize)
        return success_response(data=data, message="Locations retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching locations")


@router.get(
    "/groups",
    summary="Get groups from Keka",
    description="Admin-only endpoint that retrieves employee groups from Keka HR API.",
)
async def get_keka_groups(
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_groups(page_number=pageNumber, page_size=pageSize)
        return success_response(data=data, message="Groups retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching groups")


@router.get(
    "/group-types",
    summary="Get group types from Keka",
    description="Admin-only endpoint that retrieves group types from Keka HR API.",
)
async def get_keka_group_types(
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_group_types(page_number=pageNumber, page_size=pageSize)
        return success_response(data=data, message="Group types retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching group types")


@router.get(
    "/currencies",
    summary="Get currencies from Keka",
    description="Admin-only endpoint that retrieves configured currencies from Keka HR API.",
)
async def get_keka_currencies(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_currencies()
        return success_response(data=data, message="Currencies retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching currencies")


@router.get(
    "/notice-periods",
    summary="Get notice periods from Keka",
    description="Admin-only endpoint that retrieves configured notice periods from Keka HR API.",
)
async def get_keka_notice_periods(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_notice_periods()
        return success_response(data=data, message="Notice periods retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching notice periods")


@router.get(
    "/exit-reasons",
    summary="Get exit reasons from Keka",
    description="Admin-only endpoint that retrieves configured employee exit reasons from Keka HR API.",
)
async def get_keka_exit_reasons(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_exit_reasons()
        return success_response(data=data, message="Exit reasons retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching exit reasons")



@router.put(
    "/employees/{employee_id}/job-details",
    summary="Update employee job details in Keka",
    description="Admin-only endpoint that updates job details for an employee via PUT /hris/employees/jobdetails.",
)
@router.put(
    "/employees/{employee_id}/jobdetails",
    summary="Update employee job details in Keka (path alias)",
    description="Admin-only endpoint that updates job details for an employee via PUT /hris/employees/jobdetails.",
)
async def update_keka_employee_job_details(
    employee_id: str,
    payload: KekaJobDetailsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        is_num = employee_id.isdigit()
        data = await KekaEmployeeMappingService.update_employee_job_details_flow(
            db=db,
            payload=payload,
            user_id=int(employee_id) if is_num else None,
            keka_employee_id=employee_id if not is_num else None,
        )
        return success_response(data=data, message="Employee job details updated successfully")
    except Exception as err:
        _handle_keka_exception(err, f"updating job details for employee {employee_id}")


@router.put(
    "/employees/jobdetails",
    summary="Update employee job details in Keka (body alias)",
    description="Admin-only endpoint that updates job details for an employee via PUT /hris/employees/jobdetails.",
)
async def update_keka_employee_job_details_direct(
    payload: KekaJobDetailsUpdateRequest,
    employeeId: Optional[str] = Query(None, description="Keka employee UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        target_id = employeeId or payload.employeeId or (str(payload.user_id) if payload.user_id else None)
        if not target_id:
            raise HTTPException(status_code=400, detail="employeeId or user_id must be provided in body or query.")
        is_num = target_id.isdigit()
        data = await KekaEmployeeMappingService.update_employee_job_details_flow(
            db=db,
            payload=payload,
            user_id=int(target_id) if is_num else None,
            keka_employee_id=target_id if not is_num else None,
        )
        return success_response(data=data, message="Employee job details updated successfully")
    except Exception as err:
        _handle_keka_exception(err, "updating job details")


@router.post(
    "/employees/{employee_id}/exit-request",
    summary="Submit employee exit / deactivation request in Keka",
    description="Admin-only endpoint that initiates exit request for an employee via POST /hris/employees/{id}/exitrequest.",
)
@router.post(
    "/employees/{employee_id}/exit",
    summary="Submit employee exit / deactivation request in Keka (alias)",
    description="Admin-only endpoint that initiates exit request for an employee via POST /hris/employees/{id}/exitrequest.",
)
async def create_keka_employee_exit_request(
    employee_id: str,
    payload: KekaEmployeeExitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        is_num = employee_id.isdigit()
        data = await KekaEmployeeMappingService.create_employee_exit_flow(
            db=db,
            payload=payload,
            user_id=int(employee_id) if is_num else None,
            keka_employee_id=employee_id if not is_num else None,
        )
        return success_response(data=data, message="Employee exit request submitted successfully")
    except Exception as err:
        _handle_keka_exception(err, f"creating exit request for employee {employee_id}")



@router.get(
    "/contingent-types",
    summary="Get contingent worker types from Keka",
    description="Admin-only endpoint that retrieves contingent worker types from Keka HR API.",
)
async def get_keka_contingent_types(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_contingent_types()
        return success_response(data=data, message="Contingent types retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching contingent types")


# =============================================================================
# CATEGORY 2 – EMPLOYEE DOCUMENTS ENDPOINTS
# =============================================================================


@router.get(
    "/documents/types",
    summary="Get document types from Keka",
    description="Admin-only endpoint that retrieves document types from Keka HR API.",
)
async def get_keka_document_types(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_document_types()
        return success_response(data=data, message="Document types retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching document types")


@router.get(
    "/employees/{employee_id}/documents",
    summary="Get employee documents from Keka",
    description="Admin-only endpoint that retrieves documents list for a given employee UUID.",
)
async def get_keka_employee_documents(
    employee_id: str,
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_employee_documents(employee_id)
        return success_response(data=data, message="Employee documents retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, f"fetching documents for employee {employee_id}")


@router.get(
    "/employees/{employee_id}/documents/{document_id}/attachment",
    summary="Get employee document attachment download URL",
    description="Admin-only endpoint that retrieves document download URL from Keka HR API.",
)
async def get_keka_document_attachment_url(
    employee_id: str,
    document_id: str,
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_document_attachment_url(employee_id=employee_id, document_id=document_id)
        return success_response(data=data, message="Document attachment URL retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, f"fetching document attachment for {document_id}")


# =============================================================================
# CATEGORY 3 – LEAVE MANAGEMENT ENDPOINTS
# =============================================================================


@router.get(
    "/leave-balances",
    summary="Get leave balances from Keka",
    description="Admin-only endpoint that retrieves employee leave balances from Keka HR API.",
)
async def get_keka_leave_balances(
    employeeIds: Optional[str] = Query(None, description="Comma-separated employee UUIDs"),
    leaveTypeIds: Optional[str] = Query(None, description="Comma-separated leave type UUIDs"),
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    emp_list = [e.strip() for e in employeeIds.split(",") if e.strip()] if employeeIds else None
    lt_list = [l.strip() for l in leaveTypeIds.split(",") if l.strip()] if leaveTypeIds else None
    try:
        data = await KekaClient.get_leave_balances(
            employee_ids=emp_list,
            leave_type_ids=lt_list,
            page_number=pageNumber,
            page_size=pageSize,
        )
        return success_response(data=data, message="Leave balances retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching leave balances")


@router.get(
    "/leave-plans",
    summary="Get leave plans from Keka",
    description="Admin-only endpoint that retrieves configured leave plans from Keka HR API.",
)
async def get_keka_leave_plans(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_leave_plans()
        return success_response(data=data, message="Leave plans retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching leave plans")


@router.get(
    "/leave-requests",
    summary="Get leave requests list from Keka",
    description="Admin-only endpoint that retrieves organization leave requests from Keka HR API.",
)
async def get_keka_leave_requests(
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    employeeIds: Optional[str] = Query(None, description="Comma-separated employee UUIDs"),
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    emp_list = [e.strip() for e in employeeIds.split(",") if e.strip()] if employeeIds else None
    try:
        data = await KekaClient.get_leave_requests(
            from_date=from_date,
            to_date=to_date,
            employee_ids=emp_list,
            page_number=pageNumber,
            page_size=pageSize,
        )
        return success_response(data=data, message="Leave requests retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching leave requests")


# =============================================================================
# CATEGORY 5 – ATTENDANCE TIME ENTRY ENDPOINT
# =============================================================================


@router.post(
    "/attendance/employees/{employee_id}/timeentry",
    summary="Record attendance time entry in Keka",
    description="Admin-only endpoint that records clock-in/out for an employee via POST /attendance/employee/{id}/timeentry.",
)
async def create_keka_attendance_time_entry(
    employee_id: str,
    payload: KekaAttendanceTimeEntryCreate,
    current_user: User = Depends(require_admin),
):
    try:
        body = payload.model_dump(exclude_unset=True)
        if not body.get("employeeIdentifier"):
            body["employeeIdentifier"] = employee_id
        data = await KekaClient.create_attendance_time_entry(
            employee_id=employee_id,
            payload=body,
        )
        return success_response(data=data, message="Attendance time entry recorded successfully")
    except Exception as err:
        _handle_keka_exception(err, f"recording attendance time entry for {employee_id}")


@router.post(
    "/attendance/timeentry",
    summary="Record attendance time entry in Keka (direct alias)",
    description="Admin-only endpoint that records clock-in/out for an employee via POST /attendance/employee/{id}/timeentry.",
)
async def create_keka_attendance_time_entry_direct(
    payload: KekaAttendanceTimeEntryCreate,
    user_id: Optional[int] = Query(None, description="Optional local user ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        body = payload.model_dump(exclude_unset=True)
        target_emp_id = (body.get("employeeIdentifier") or "").strip()
        effective_user_id = user_id or getattr(payload, "user_id", None)

        if effective_user_id and not target_emp_id:
            summary = await KekaAttendanceService.push_time_entry_for_user(
                db=db,
                user_id=effective_user_id,
                timestamp=body.get("timestamp"),
                punch_status=body.get("punchStatus", 0),
                note=body.get("note"),
            )
            return success_response(data=summary, message="Attendance time entry recorded successfully")

        if not target_emp_id:
            raise HTTPException(status_code=400, detail="employeeIdentifier or user_id is required.")

        data = await KekaClient.create_attendance_time_entry(
            employee_id=target_emp_id,
            payload=body,
        )
        return success_response(data=data, message="Attendance time entry recorded successfully")
    except Exception as err:
        _handle_keka_exception(err, "recording attendance time entry")


# =============================================================================
# CATEGORY 6 – WEEKLY OFF POLICIES ENDPOINT
# =============================================================================


@router.get(
    "/weekly-off-policies",
    summary="Get weekly off policies from Keka",
    description="Admin-only endpoint that retrieves weekly off policies from Keka HR API.",
)
async def get_keka_weekly_off_policies(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_weekly_off_policies()
        return success_response(data=data, message="Weekly off policies retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching weekly off policies")


# =============================================================================
# CATEGORY 7 – SHIFT POLICIES ENDPOINT
# =============================================================================


@router.get(
    "/shift-policies",
    summary="Get shift policies from Keka",
    description="Admin-only endpoint that retrieves shift policies from Keka HR API.",
)
async def get_keka_shift_policies(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_shift_policies()
        return success_response(data=data, message="Shift policies retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching shift policies")


# =============================================================================
# CATEGORY 8 – CAPTURE SCHEME ENDPOINT
# =============================================================================


@router.get(
    "/capture-scheme",
    summary="Get capture scheme from Keka",
    description="Admin-only endpoint that retrieves attendance capture schemes from Keka HR API.",
)
async def get_keka_capture_scheme(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_capture_schemes()
        return success_response(data=data, message="Capture schemes retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching capture schemes")


# =============================================================================
# CATEGORY 9 – HOLIDAY CALENDAR ENDPOINTS
# =============================================================================


@router.get(
    "/holiday-calendars",
    summary="Get holiday calendars from Keka",
    description="Admin-only endpoint that retrieves holiday calendars from Keka HR API.",
)
async def get_keka_holiday_calendars(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_holiday_calendars()
        return success_response(data=data, message="Holiday calendars retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching holiday calendars")


@router.get(
    "/holiday-calendars/{calendar_id}/holidays",
    summary="Get holidays list for a calendar from Keka",
    description="Admin-only endpoint that retrieves holidays for a calendar from Keka HR API.",
)
async def get_keka_calendar_holidays(
    calendar_id: str,
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_calendar_holidays(calendar_id)
        return success_response(data=data, message="Holidays retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, f"fetching holidays for calendar {calendar_id}")


# =============================================================================
# CATEGORY 10 – REGULARISATION ENDPOINT
# =============================================================================


@router.get(
    "/regularisation-requests",
    summary="Get regularisation requests from Keka",
    description="Admin-only endpoint that retrieves attendance regularisation requests from Keka HR API.",
)
async def get_keka_regularisation_requests(
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    employeeIds: Optional[str] = Query(None, description="Comma-separated employee UUIDs"),
    lastModified: Optional[str] = Query(None, description="Last modified filter"),
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    emp_list = [e.strip() for e in employeeIds.split(",") if e.strip()] if employeeIds else None
    try:
        data = await KekaClient.get_regularisation_requests(
            from_date=from_date,
            to_date=to_date,
            employee_ids=emp_list,
            last_modified=lastModified,
            page_number=pageNumber,
            page_size=pageSize,
        )
        return success_response(data=data, message="Regularisation requests retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching regularisation requests")


# =============================================================================
# CATEGORY 11 – PENALISATION POLICIES ENDPOINT
# =============================================================================


@router.get(
    "/penalisation-policies",
    summary="Get penalisation policies from Keka",
    description="Admin-only endpoint that retrieves attendance penalisation / tracking policies from Keka HR API.",
)
async def get_keka_penalisation_policies(
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaClient.get_penalisation_policies()
        return success_response(data=data, message="Penalisation policies retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching penalisation policies")


# =============================================================================
# CATEGORY 12 – WORK FROM HOME ENDPOINTS
# =============================================================================


@router.get(
    "/wfh",
    summary="Get WFH requests from Keka",
    description="Admin-only endpoint that retrieves Work From Home requests from Keka HR API.",
)
async def get_keka_wfh_requests(
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    employeeIds: Optional[str] = Query(None, description="Comma-separated employee UUIDs"),
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    emp_list = [e.strip() for e in employeeIds.split(",") if e.strip()] if employeeIds else None
    try:
        data = await KekaClient.get_wfh_requests(
            from_date=from_date,
            to_date=to_date,
            employee_ids=emp_list,
            page_number=pageNumber,
            page_size=pageSize,
        )
        return success_response(data=data, message="WFH requests retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching WFH requests")


@router.post(
    "/wfh",
    summary="Submit WFH request in Keka",
    description="Admin-only endpoint that submits a Work From Home request via POST /time/wfh.",
)
async def create_keka_wfh_request(
    payload: KekaWFHCreateRequest,
    user_id: Optional[int] = Query(None, description="Optional local user ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaEmployeeMappingService.create_wfh_flow(db=db, payload=payload, user_id=user_id)
        return success_response(data=data, message="WFH request submitted successfully")
    except Exception as err:
        _handle_keka_exception(err, "submitting WFH request")


# =============================================================================
# CATEGORY 13 – ON DUTY ENDPOINTS
# =============================================================================


@router.get(
    "/od",
    summary="Get On Duty requests from Keka",
    description="Admin-only endpoint that retrieves On Duty requests from Keka HR API.",
)
async def get_keka_od_requests(
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    employeeIds: Optional[str] = Query(None, description="Comma-separated employee UUIDs"),
    pageNumber: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    emp_list = [e.strip() for e in employeeIds.split(",") if e.strip()] if employeeIds else None
    try:
        data = await KekaClient.get_od_requests(
            from_date=from_date,
            to_date=to_date,
            employee_ids=emp_list,
            page_number=pageNumber,
            page_size=pageSize,
        )
        return success_response(data=data, message="On Duty requests retrieved successfully")
    except Exception as err:
        _handle_keka_exception(err, "fetching On Duty requests")


@router.post(
    "/od",
    summary="Submit On Duty request in Keka",
    description="Admin-only endpoint that submits an On Duty request via POST /time/od.",
)
async def create_keka_od_request(
    payload: KekaODCreateRequest,
    user_id: Optional[int] = Query(None, description="Optional local user ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        data = await KekaEmployeeMappingService.create_od_flow(db=db, payload=payload, user_id=user_id)
        return success_response(data=data, message="On Duty request submitted successfully")
    except Exception as err:
        _handle_keka_exception(err, "submitting On Duty request")



# =============================================================================
# CATEGORY 14 – SYSTEM DEEP SYNCHRONIZATION ENDPOINTS
# =============================================================================


@router.post(
    "/sync/employees",
    summary="Synchronize employees from Keka into local database",
    description="Admin-only endpoint that pulls all active/resigned employees from Keka and updates local User records, Department mappings, and keka_employee_mappings.",
)
async def sync_keka_employees(
    update_existing: bool = Query(True, description="Update existing users' details"),
    create_missing: bool = Query(False, description="Create new users if not found in local system"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaService.sync_employees_from_keka(
            db, update_existing=update_existing, create_missing=create_missing
        )
        return success_response(data=summary, message="Employee synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing employees")


@router.post(
    "/sync/departments",
    summary="Synchronize departments from Keka into local database",
    description="Admin-only endpoint that pulls departments from Keka and creates any missing departments in the local database.",
)
async def sync_keka_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaService.sync_departments_from_keka(db)
        return success_response(data=summary, message="Department synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing departments")


@router.post(
    "/sync/leave-types",
    summary="Synchronize leave types from Keka into local database",
    description="Admin-only endpoint that pulls leave types from Keka and links keka_leave_type_id in the local leave_types table.",
)
async def sync_keka_leave_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaService.sync_leave_types_from_keka(db)
        return success_response(data=summary, message="Leave type synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing leave types")


@router.post(
    "/sync/holidays",
    summary="Synchronize holidays from Keka into local database",
    description="Admin-only endpoint that pulls holidays from Keka calendars and inserts missing holidays into the local holidays table.",
)
async def sync_keka_holidays(
    calendar_id: Optional[str] = Query(None, description="Optional Keka holiday calendar UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaService.sync_holidays_from_keka(db, calendar_id=calendar_id)
        return success_response(data=summary, message="Holiday synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing holidays")


@router.post(
    "/sync/leaves/pending",
    summary="Push unsynced approved leaves to Keka",
    description="Admin-only endpoint that identifies local approved leave requests not yet synced to Keka and attempts to push them.",
)
async def sync_pending_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaLeaveService.sync_all_unsynced_leaves(db)
        return success_response(data=summary, message="Pending leave synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing pending leaves")


@router.post(
    "/sync/leaves/statuses",
    summary="Pull leave statuses from Keka and update local leave requests",
    description="Admin-only endpoint that fetches leave requests from Keka and synchronizes their approval status to local records.",
)
async def sync_leave_statuses(
    from_date: Optional[str] = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaLeaveService.sync_leave_statuses_from_keka(db, from_date=from_date, to_date=to_date)
        return success_response(data=summary, message="Leave status synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing leave statuses")


@router.post(
    "/sync/weekly-off",
    summary="Synchronize Keka weekly off policy with company Working Calendar",
    description="Admin-only endpoint that pulls weekly off rules from Keka and updates local WorkingCalendar working_days JSON.",
)
async def sync_weekly_off_policy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaAttendanceService.sync_weekly_off_policy_to_calendar(db)
        return success_response(data=summary, message="Weekly off policy synchronization completed")
    except Exception as err:
        _handle_keka_exception(err, "synchronizing weekly off policy")


@router.post(
    "/attendance/push-time-entry",
    summary="Push attendance time entry for internal employee",
    description="Pushes a clock-in/out punch to Keka by resolving local user_id to Keka UUID.",
)
async def push_time_entry_for_employee(
    user_id: int = Query(..., description="Local user ID"),
    timestamp: str = Query(..., description="Timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)"),
    punch_status: int = Query(0, description="0=Auto, 1=In, 2=Out"),
    note: Optional[str] = Query(None, description="Optional note"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        summary = await KekaAttendanceService.push_time_entry_for_user(
            db=db,
            user_id=user_id,
            timestamp=timestamp,
            punch_status=punch_status,
            note=note,
        )
        return success_response(data=summary, message="Attendance time entry pushed successfully")
    except Exception as err:
        _handle_keka_exception(err, "pushing attendance time entry")



