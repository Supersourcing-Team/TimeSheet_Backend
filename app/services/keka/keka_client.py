import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.keka.keka_auth import KekaAuthError, KekaAuthManager

logger = logging.getLogger(__name__)


class KekaAPIError(Exception):
    """Exception raised when a Keka API call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class KekaClient:
    """
    HTTP client for interacting with Keka HR API v1.
    Handles token injection, automatic retry on 401, rate limit detection, and pagination.
    """

    @classmethod
    def get_base_url(cls) -> str:
        """Constructs Keka API base URL based on company subdomain and environment."""
        from pathlib import Path
        from dotenv import dotenv_values
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        env_vals = dotenv_values(env_path) if env_path.exists() else {}

        company = (
            os.getenv("KEKA_COMPANY_NAME")
            or os.getenv("KEKA_COMPANY")
            or env_vals.get("KEKA_COMPANY_NAME")
            or env_vals.get("KEKA_COMPANY")
            or settings.KEKA_COMPANY_NAME
            or getattr(settings, "KEKA_COMPANY", "")
            or ""
        ).strip()
        if not company:
            raise KekaAPIError("KEKA_COMPANY_NAME is not configured in settings or environment.", status_code=500)

        env = (settings.KEKA_ENVIRONMENT or "production").lower()
        if env == "sandbox":
            return f"https://{company}.kekademo.com/api/v1"
        return f"https://{company}.keka.com/api/v1"

    @classmethod
    async def request(
        cls,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Executes an authenticated HTTP request against Keka API.
        Automatically injects Bearer token and retries once if token expired (HTTP 401).
        """
        base_url = cls.get_base_url()
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        for attempt in range(2):
            force_refresh = attempt > 0
            token = await KekaAuthManager.get_access_token(force_refresh=force_refresh)

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=headers,
                    )

                # If token expired on server-side despite local validity, retry with forced refresh
                if response.status_code == 401 and attempt == 0:
                    logger.warning("Received 401 from Keka API; refreshing token and retrying...")
                    continue

                if response.status_code == 401:
                    logger.error("Keka API authentication failed (HTTP 401) after retry.")
                    raise KekaAPIError(
                        "Keka authentication failed. Invalid credentials or unauthorized token.",
                        status_code=401,
                    )

                if response.status_code == 403:
                    logger.error("Keka API access forbidden (HTTP 403). Check API key permissions/scopes.")
                    raise KekaAPIError(
                        "Keka API access forbidden. Insufficient permissions/scopes for this resource.",
                        status_code=403,
                    )

                if response.status_code == 404:
                    logger.error("Keka resource not found (HTTP 404): %s", url)
                    raise KekaAPIError(
                        "Keka API resource not found (HTTP 404).",
                        status_code=404,
                    )

                if response.status_code == 429:
                    logger.error("Keka API rate limit reached (50 requests/minute exceeded).")
                    raise KekaAPIError(
                        "Keka API rate limit exceeded (HTTP 429). Please wait before retrying.",
                        status_code=429,
                    )

                if response.status_code >= 500:
                    logger.error("Keka upstream server error (HTTP %s): %s", response.status_code, response.text)
                    raise KekaAPIError(
                        f"Keka upstream server error (HTTP {response.status_code}). Please try again later.",
                        status_code=response.status_code,
                    )

                if response.status_code not in (200, 201, 204):
                    error_body = response.text
                    try:
                        error_body = response.json()
                    except Exception:
                        pass
                    logger.error(
                        "Keka API error on %s %s: status %s, body: %s",
                        method,
                        url,
                        response.status_code,
                        error_body,
                    )
                    raise KekaAPIError(
                        f"Keka API error ({response.status_code}): {error_body}",
                        status_code=response.status_code,
                        details=error_body,
                    )

                if response.status_code == 204:
                    return {"succeeded": True, "data": []}

                try:
                    return response.json()
                except Exception as exc:
                    logger.error("Failed to parse JSON response from Keka API: %s", exc)
                    raise KekaAPIError("Malformed response received from Keka API.", status_code=502) from exc

            except httpx.TimeoutException as exc:
                logger.error("Timeout connecting to Keka API (%s): %s", url, exc)
                raise KekaAPIError("Keka API request timed out.", status_code=504) from exc
            except httpx.RequestError as exc:
                logger.error("Network error while connecting to Keka API (%s): %s", url, exc)
                raise KekaAPIError(f"Network error calling Keka API: {str(exc)}", status_code=502) from exc

        raise KekaAPIError("Failed to authenticate with Keka API after retry.", status_code=401)

    @classmethod
    async def get(cls, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Helper for GET requests."""
        return await cls.request("GET", endpoint, params=params)

    @classmethod
    async def post(
        cls, endpoint: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Helper for POST requests."""
        return await cls.request("POST", endpoint, params=params, json_data=json_data)

    @classmethod
    async def put(
        cls, endpoint: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Helper for PUT requests."""
        return await cls.request("PUT", endpoint, params=params, json_data=json_data)

    @classmethod
    async def create_leave_request(
        cls,
        employee_id: str,
        from_date: str,
        to_date: str,
        leave_type_id: str,
        reason: str,
        requested_by: Optional[str] = None,
        from_session: int = 0,
        to_session: int = 1,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a leave request in Keka via POST /time/leaverequests.
        Keka SessionType enum: 0 = First Half (Session 1), 1 = Second Half (Session 2).
        Returns the Keka response object, where 'data' typically holds the Keka leave request ID.
        """
        payload: Dict[str, Any] = {
            "employeeId": employee_id,
            "requestedBy": requested_by or employee_id,
            "fromDate": from_date,
            "toDate": to_date,
            "fromSession": from_session,
            "toSession": to_session,
            "leaveTypeId": leave_type_id,
            "reason": reason,
        }
        if note:
            payload["note"] = note

        return await cls.post("/time/leaverequests", json_data=payload)

    @classmethod
    async def get_leave_types(cls) -> Dict[str, Any]:
        """
        Calls GET /time/leavetypes to retrieve all configured leave types in Keka.
        Returns the Keka response object containing list of leave types.
        """
        return await cls.get("/time/leavetypes")

    @classmethod
    async def get_employees(
        cls,
        page_number: int = 1,
        page_size: int = 100,
        employment_status: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calls GET /hris/employees to fetch a single page of employee records.
        Returns a structured dictionary with pagination metadata.
        """
        valid_page_number = max(1, page_number)
        valid_page_size = min(max(1, page_size), 200)  # Keka max is 200

        params: Dict[str, Any] = {
            "pageNumber": valid_page_number,
            "pageSize": valid_page_size,
        }
        if employment_status:
            params["employmentStatus"] = employment_status
        if last_modified:
            params["lastModified"] = last_modified

        raw_response = await cls.get("/hris/employees", params=params)

        if not isinstance(raw_response, dict):
            raise KekaAPIError("Malformed employee response structure received from Keka.", status_code=502)

        data = raw_response.get("data")
        if data is None:
            data = []
        elif not isinstance(data, list):
            raise KekaAPIError("Unexpected employee data format received from Keka.", status_code=502)

        total_records = raw_response.get("totalRecords")
        if total_records is None:
            total_records = len(data)

        total_pages = raw_response.get("totalPages")
        if total_pages is None:
            total_pages = 1 if len(data) > 0 else 0

        return {
            "pageNumber": raw_response.get("pageNumber", valid_page_number),
            "pageSize": raw_response.get("pageSize", valid_page_size),
            "totalRecords": total_records,
            "totalPages": total_pages,
            "data": data,
        }

    @classmethod
    async def get_all_employees(
        cls,
        page_size: int = 200,
        employment_status: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Automatically follows pagination until all employee pages are retrieved.
        Respects Keka rate limits with safe pacing and handles empty/single pages cleanly.
        Does NOT write anything to database.
        """
        batch_size = min(max(1, page_size), 200)
        all_employees: List[Dict[str, Any]] = []
        current_page = 1
        total_pages_retrieved = 0

        while True:
            page_result = await cls.get_employees(
                page_number=current_page,
                page_size=batch_size,
                employment_status=employment_status,
                last_modified=last_modified,
            )

            employees = page_result.get("data", [])
            total_records = page_result.get("totalRecords", 0)
            total_pages = page_result.get("totalPages", 1)

            total_pages_retrieved += 1

            if employees:
                all_employees.extend(employees)

            # Termination condition:
            # 1. No more records in this page
            # 2. We reached or exceeded the declared totalPages
            # 3. Accumulated records reached or exceeded declared totalRecords (when positive)
            if not employees or current_page >= total_pages or (total_records > 0 and len(all_employees) >= total_records):
                break

            current_page += 1

            # Micro-sleep to pace requests responsibly and protect against 429 rate limit
            await asyncio.sleep(0.02)

        return {
            "totalRecords": len(all_employees),
            "totalPagesRetrieved": total_pages_retrieved,
            "data": all_employees,
        }

    @classmethod
    async def get_attendance(
        cls,
        from_date: str,
        to_date: str,
        employee_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Calls GET /time/attendance to fetch a single page of attendance records.
        Returns structured dictionary with pagination metadata and attendance data.
        """
        valid_page_number = max(1, page_number)
        valid_page_size = min(max(1, page_size), 200)

        params: Dict[str, Any] = {
            "from": from_date,
            "to": to_date,
            "pageNumber": valid_page_number,
            "pageSize": valid_page_size,
        }
        if employee_ids:
            if isinstance(employee_ids, list):
                params["employeeIds"] = ",".join(employee_ids)
            else:
                params["employeeIds"] = str(employee_ids)

        raw_response = await cls.get("/time/attendance", params=params)

        if not isinstance(raw_response, dict):
            raise KekaAPIError("Malformed attendance response structure received from Keka.", status_code=502)

        data = raw_response.get("data")
        if data is None:
            data = []
        elif not isinstance(data, list):
            raise KekaAPIError("Unexpected attendance data format received from Keka.", status_code=502)

        total_records = raw_response.get("totalRecords")
        if total_records is None:
            total_records = len(data)

        total_pages = raw_response.get("totalPages")
        if total_pages is None:
            total_pages = 1 if len(data) > 0 else 0

        return {
            "pageNumber": raw_response.get("pageNumber", valid_page_number),
            "pageSize": raw_response.get("pageSize", valid_page_size),
            "totalRecords": total_records,
            "totalPages": total_pages,
            "data": data,
        }

    @classmethod
    async def get_all_attendance(
        cls,
        from_date: str,
        to_date: str,
        employee_ids: Optional[List[str]] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Automatically follows pagination until all attendance pages for the given date window are retrieved.
        Returns a flat list of employee attendance records.
        """
        batch_size = min(max(1, page_size), 200)
        all_records: List[Dict[str, Any]] = []
        current_page = 1

        while True:
            page_result = await cls.get_attendance(
                from_date=from_date,
                to_date=to_date,
                employee_ids=employee_ids,
                page_number=current_page,
                page_size=batch_size,
            )

            records = page_result.get("data", [])
            total_records = page_result.get("totalRecords", 0)
            total_pages = page_result.get("totalPages", 1)

            if records:
                all_records.extend(records)

            if not records or current_page >= total_pages or (total_records > 0 and len(all_records) >= total_records):
                break

            current_page += 1
            await asyncio.sleep(0.02)

        return all_records

    @classmethod
    async def get_all_pages(
        cls,
        fetch_func,
        *args,
        page_size: int = 100,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Generic pagination iterator that calls fetch_func(..., page_number=N, page_size=M)
        and collects all records across pages.
        """
        all_records: List[Dict[str, Any]] = []
        page = 1
        while True:
            res = await fetch_func(*args, page_number=page, page_size=page_size, **kwargs)
            if isinstance(res, list):
                all_records.extend(res)
                break
            records = res.get("data", []) if isinstance(res, dict) else []
            if records:
                all_records.extend(records)
            total_pages = res.get("totalPages", 1) if isinstance(res, dict) else 1
            if not records or page >= total_pages:
                break
            page += 1
            await asyncio.sleep(0.01)
        return all_records

    @classmethod
    async def test_connection(cls) -> Dict[str, Any]:
        """
        Tests authentication and pulls a sample of employee records to verify end-to-end connectivity.
        """
        if not KekaAuthManager.is_configured():
            creds = KekaAuthManager.get_credentials()
            missing = [k for k, v in creds.items() if not v]
            return {
                "status": "unconfigured",
                "message": f"Keka integration is not configured. Missing: {', '.join(missing)}",
                "missing_fields": missing,
            }

        try:
            # Fetch small sample
            data = await cls.get_employees(page_number=1, page_size=3)
            employees = data.get("data", []) or []

            sample_summary: List[Dict[str, Any]] = []
            for emp in employees:
                sample_summary.append({
                    "id": emp.get("id"),
                    "employeeNumber": emp.get("employeeNumber"),
                    "displayName": emp.get("displayName") or f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip(),
                    "email": emp.get("email"),
                    "department": emp.get("department") or emp.get("departmentName"),
                })

            return {
                "status": "connected",
                "message": "Successfully connected to Keka API and fetched sample records.",
                "company": (os.getenv("KEKA_COMPANY_NAME") or settings.KEKA_COMPANY_NAME),
                "environment": settings.KEKA_ENVIRONMENT,
                "token_endpoint": KekaAuthManager.get_token_url(),
                "api_base_url": cls.get_base_url(),
                "total_records_in_keka": data.get("totalRecords", len(employees)),
                "sample_count": len(sample_summary),
                "sample_employees": sample_summary,
            }

        except (KekaAuthError, KekaAPIError) as err:
            return {
                "status": "error",
                "message": str(err),
                "company": (os.getenv("KEKA_COMPANY_NAME") or settings.KEKA_COMPANY_NAME),
                "environment": settings.KEKA_ENVIRONMENT,
            }

    # =========================================================================
    # CATEGORY 1 – HR CORE & EMPLOYEE LIFECYCLE
    # =========================================================================

    @classmethod
    async def get_employee(cls, employee_id: str) -> Dict[str, Any]:
        """Calls GET /hris/employees/{employeeId} to retrieve employee details."""
        return await cls.get(f"/hris/employees/{employee_id}")

    @classmethod
    async def create_employee(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calls POST /hris/employees to create a new employee in Keka."""
        return await cls.post("/hris/employees", json_data=payload)

    @classmethod
    async def get_departments(cls, page_number: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Calls GET /hris/departments to fetch department records."""
        params = {"pageNumber": max(1, page_number), "pageSize": min(max(1, page_size), 200)}
        return await cls.get("/hris/departments", params=params)

    @classmethod
    async def get_job_titles(cls, page_number: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Calls GET /hris/jobtitles to fetch job title records."""
        params = {"pageNumber": max(1, page_number), "pageSize": min(max(1, page_size), 200)}
        return await cls.get("/hris/jobtitles", params=params)

    @classmethod
    async def get_locations(cls, page_number: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Calls GET /hris/locations to fetch company location records."""
        params = {"pageNumber": max(1, page_number), "pageSize": min(max(1, page_size), 200)}
        return await cls.get("/hris/locations", params=params)

    @classmethod
    async def get_groups(cls, page_number: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Calls GET /hris/groups to fetch employee groups."""
        params = {"pageNumber": max(1, page_number), "pageSize": min(max(1, page_size), 200)}
        return await cls.get("/hris/groups", params=params)

    @classmethod
    async def get_group_types(cls, page_number: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Calls GET /hris/grouptypes to fetch group types."""
        params = {"pageNumber": max(1, page_number), "pageSize": min(max(1, page_size), 200)}
        return await cls.get("/hris/grouptypes", params=params)

    @classmethod
    async def get_currencies(cls) -> Dict[str, Any]:
        """Calls GET /hris/currencies to fetch supported currencies."""
        return await cls.get("/hris/currencies")

    @classmethod
    async def get_notice_periods(cls) -> Dict[str, Any]:
        """Calls GET /hris/noticeperiods to fetch configured notice periods."""
        return await cls.get("/hris/noticeperiods")

    @classmethod
    async def get_exit_reasons(cls) -> Dict[str, Any]:
        """Calls GET /hris/exitreasons to fetch employee exit reasons."""
        return await cls.get("/hris/exitreasons")

    @classmethod
    async def get_employee_update_fields(cls) -> Dict[str, Any]:
        """Calls GET /hris/employees/updatefields to fetch supported employee update fields."""
        return await cls.get("/hris/employees/updatefields")

    @classmethod
    async def update_employee_job_details(cls, employee_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls PUT /hris/employees/jobdetails?employeeId={employeeId}
        Updates job details for an existing employee.
        """
        params = {"employeeId": employee_id}
        return await cls.put("/hris/employees/jobdetails", json_data=payload, params=params)

    @classmethod
    async def create_employee_exit_request(cls, employee_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls POST /hris/employees/{id}/exitrequest to deactivate/initiate exit for an employee.
        """
        return await cls.post(f"/hris/employees/{employee_id}/exitrequest", json_data=payload)

    @classmethod
    async def get_contingent_types(cls) -> Dict[str, Any]:
        """Calls GET /hris/contingenttypes to fetch contingent worker types."""
        return await cls.get("/hris/contingenttypes")

    # =========================================================================
    # CATEGORY 2 – EMPLOYEE DOCUMENTS
    # =========================================================================

    @classmethod
    async def get_document_types(cls) -> Dict[str, Any]:
        """Calls GET /hris/documents/types to fetch supported document types."""
        return await cls.get("/hris/documents/types")

    @classmethod
    async def get_employee_documents(cls, employee_id: str) -> Dict[str, Any]:
        """Calls GET /hris/employees/{employeeId}/documents to retrieve an employee's documents."""
        return await cls.get(f"/hris/employees/{employee_id}/documents")

    @classmethod
    async def get_document_attachment_url(cls, employee_id: str, document_id: str) -> Dict[str, Any]:
        """Calls GET /hris/employees/{employeeId}/documents/{documentId}/attachment for download URL."""
        return await cls.get(f"/hris/employees/{employee_id}/documents/{document_id}/attachment")

    # =========================================================================
    # CATEGORY 3 – LEAVE MANAGEMENT
    # =========================================================================

    @classmethod
    async def get_leave_balances(
        cls,
        employee_ids: Optional[List[str]] = None,
        leave_type_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Calls GET /time/leavebalance to retrieve employee leave balances."""
        params: Dict[str, Any] = {
            "pageNumber": max(1, page_number),
            "pageSize": min(max(1, page_size), 200),
        }
        if employee_ids:
            params["employeeIds"] = ",".join(employee_ids) if isinstance(employee_ids, list) else str(employee_ids)
        if leave_type_ids:
            params["leaveTypeIds"] = ",".join(leave_type_ids) if isinstance(leave_type_ids, list) else str(leave_type_ids)
        return await cls.get("/time/leavebalance", params=params)

    @classmethod
    async def get_leave_plans(cls) -> Dict[str, Any]:
        """Calls GET /time/leaveplans to retrieve configured leave plans."""
        return await cls.get("/time/leaveplans")

    @classmethod
    async def get_leave_requests(
        cls,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        employee_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Calls GET /time/leaverequests to retrieve leave requests across date range."""
        params: Dict[str, Any] = {
            "pageNumber": max(1, page_number),
            "pageSize": min(max(1, page_size), 200),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if employee_ids:
            params["employeeIds"] = ",".join(employee_ids) if isinstance(employee_ids, list) else str(employee_ids)
        return await cls.get("/time/leaverequests", params=params)

    # =========================================================================
    # CATEGORY 5 – ATTENDANCE TIME ENTRY
    # =========================================================================

    @classmethod
    async def create_attendance_time_entry(
        cls,
        employee_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calls POST /attendance/employee/{routeEmployeeId}/timeentry to record clock-in/out.
        """
        return await cls.post(f"/attendance/employee/{employee_id}/timeentry", json_data=payload)

    @classmethod
    async def log_attendance_time_entry(
        cls,
        route_employee_id: str,
        timestamp: str,
        punch_status: int = 0,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Helper method to format payload and call POST /attendance/employee/{routeEmployeeId}/timeentry.
        """
        payload = {
            "timestamp": timestamp,
            "punchStatus": punch_status,
            "note": note,
        }
        return await cls.create_attendance_time_entry(employee_id=route_employee_id, payload=payload)


    # =========================================================================
    # CATEGORY 6 – WEEKLY OFF POLICIES
    # =========================================================================

    @classmethod
    async def get_weekly_off_policies(cls) -> Dict[str, Any]:
        """Calls GET /time/weeklyoffpolicies to retrieve configured weekly off policies."""
        return await cls.get("/time/weeklyoffpolicies")

    # =========================================================================
    # CATEGORY 7 – SHIFT POLICIES
    # =========================================================================

    @classmethod
    async def get_shift_policies(cls) -> Dict[str, Any]:
        """Calls GET /time/shiftpolicies to retrieve configured shift policies."""
        return await cls.get("/time/shiftpolicies")

    # =========================================================================
    # CATEGORY 8 – CAPTURE SCHEME
    # =========================================================================

    @classmethod
    async def get_capture_schemes(cls) -> Dict[str, Any]:
        """Calls GET /time/capturescheme to retrieve attendance capture schemes."""
        return await cls.get("/time/capturescheme")

    # =========================================================================
    # CATEGORY 9 – HOLIDAY CALENDAR
    # =========================================================================

    @classmethod
    async def get_holiday_calendars(cls) -> Dict[str, Any]:
        """Calls GET /time/holidayscalendar to retrieve holiday calendars."""
        return await cls.get("/time/holidayscalendar")

    @classmethod
    async def get_calendar_holidays(cls, calendar_id: str) -> Dict[str, Any]:
        """Calls GET /time/holidayscalendar/{calendarId}/holidays to retrieve holidays for a calendar."""
        return await cls.get(f"/time/holidayscalendar/{calendar_id}/holidays")

    # =========================================================================
    # CATEGORY 10 – REGULARISATION
    # =========================================================================

    @classmethod
    async def get_regularisation_requests(
        cls,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        employee_ids: Optional[List[str]] = None,
        last_modified: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Calls GET /time/regularisationrequests to retrieve attendance regularisation requests."""
        params: Dict[str, Any] = {
            "pageNumber": max(1, page_number),
            "pageSize": min(max(1, page_size), 200),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if employee_ids:
            params["employeeIds"] = ",".join(employee_ids) if isinstance(employee_ids, list) else str(employee_ids)
        if last_modified:
            params["lastModified"] = last_modified
        return await cls.get("/time/regularisationrequests", params=params)

    # =========================================================================
    # CATEGORY 11 – PENALISATION POLICIES
    # =========================================================================

    @classmethod
    async def get_penalisation_policies(cls) -> Dict[str, Any]:
        """Calls GET /time/penalisationpolicies to retrieve attendance penalisation policies."""
        return await cls.get("/time/penalisationpolicies")

    # =========================================================================
    # CATEGORY 12 – WORK FROM HOME
    # =========================================================================

    @classmethod
    async def get_wfh_requests(
        cls,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        employee_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Calls GET /time/wfh to retrieve WFH requests across date range."""
        params: Dict[str, Any] = {
            "pageNumber": max(1, page_number),
            "pageSize": min(max(1, page_size), 200),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if employee_ids:
            params["employeeIds"] = ",".join(employee_ids) if isinstance(employee_ids, list) else str(employee_ids)
        return await cls.get("/time/wfh", params=params)

    @classmethod
    async def create_wfh_request(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calls POST /time/wfh to submit a Work From Home request."""
        return await cls.post("/time/wfh", json_data=payload)

    # =========================================================================
    # CATEGORY 13 – ON DUTY
    # =========================================================================

    @classmethod
    async def get_od_requests(
        cls,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        employee_ids: Optional[List[str]] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Calls GET /time/od to retrieve On Duty requests across date range."""
        params: Dict[str, Any] = {
            "pageNumber": max(1, page_number),
            "pageSize": min(max(1, page_size), 200),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if employee_ids:
            params["employeeIds"] = ",".join(employee_ids) if isinstance(employee_ids, list) else str(employee_ids)
        return await cls.get("/time/od", params=params)

    @classmethod
    async def create_od_request(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calls POST /time/od to submit an On Duty request."""
        return await cls.post("/time/od", json_data=payload)

