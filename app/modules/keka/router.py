import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import success_response
from app.core.database import get_db
from app.dependencies.permissions import require_admin
from app.modules.keka.schema import (
    KekaAllEmployeesResponse,
    KekaEmployeeMappingCreate,
    KekaEmployeeMappingDeleteResponse,
    KekaEmployeeMappingListResponse,
    KekaEmployeeMappingResponse,
    KekaMappingPreviewResponse,
    KekaPaginatedEmployeesResponse,
)
from app.modules.keka.service import KekaEmployeeMappingService
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
