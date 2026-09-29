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
        company = (os.getenv("KEKA_COMPANY_NAME") or settings.KEKA_COMPANY_NAME or "").strip()
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
