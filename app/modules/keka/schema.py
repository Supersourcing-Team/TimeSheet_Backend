from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, model_validator


class KekaEmployeeResponse(BaseModel):
    """Schema for individual Keka employee details."""

    id: str
    employeeNumber: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    displayName: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    jobTitle: Optional[str] = None
    dateOfJoining: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Shallow copy so original dictionary is not mutated
        clean_data = dict(data)

        # 1. Normalize status from employmentStatus or status
        if not clean_data.get("status"):
            raw_status = clean_data.get("employmentStatus")
            if raw_status is not None:
                # Keka might return integer enum (e.g. 0, 1) or string ("Working", "Relieved")
                status_map = {0: "Working", 1: "Relieved", 2: "Notice Period", 3: "Probation"}
                clean_data["status"] = status_map.get(raw_status, str(raw_status))

        # 2. Normalize department (handle string, object, or departmentName)
        raw_dept = clean_data.get("department")
        if isinstance(raw_dept, dict):
            clean_data["department"] = (
                raw_dept.get("name")
                or raw_dept.get("title")
                or raw_dept.get("departmentName")
                or None
            )
        elif not raw_dept and clean_data.get("departmentName"):
            clean_data["department"] = clean_data.get("departmentName")

        # 3. Normalize jobTitle from title / designation if missing
        if not clean_data.get("jobTitle"):
            clean_data["jobTitle"] = (
                clean_data.get("title")
                or clean_data.get("designation")
                or clean_data.get("jobTitleName")
                or None
            )

        # 4. Normalize dateOfJoining from joiningDate if missing
        if not clean_data.get("dateOfJoining"):
            clean_data["dateOfJoining"] = (
                clean_data.get("joiningDate")
                or clean_data.get("hireDate")
                or None
            )

        # 5. Normalize displayName if missing
        if not clean_data.get("displayName"):
            first = clean_data.get("firstName") or ""
            last = clean_data.get("lastName") or ""
            full = f"{first} {last}".strip()
            if full:
                clean_data["displayName"] = full

        return clean_data


class KekaPaginatedEmployeesResponse(BaseModel):
    """Schema for paginated employee responses from Keka."""

    pageNumber: int
    pageSize: int
    totalRecords: int
    totalPages: int
    data: List[KekaEmployeeResponse]

    model_config = ConfigDict(extra="ignore")


class KekaAllEmployeesResponse(BaseModel):
    """Schema for retrieved complete employee list across all pages."""

    totalRecords: int
    totalPagesRetrieved: int
    data: List[KekaEmployeeResponse]

    model_config = ConfigDict(extra="ignore")


class KekaEmployeeMappingResponse(BaseModel):
    """Schema for a single Keka employee to local user mapping record."""

    id: int
    keka_employee_id: str
    local_user_id: int
    keka_employee_number: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    sync_status: str
    created_at: datetime
    updated_at: datetime
    local_user_email: Optional[str] = None
    local_user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def populate_local_user_fields(cls, data: Any) -> Any:
        if hasattr(data, "user") and data.user is not None:
            # SQLAlchemy model object
            user = data.user
            first = getattr(user, "first_name", "") or ""
            last = getattr(user, "last_name", "") or ""
            return {
                "id": data.id,
                "keka_employee_id": data.keka_employee_id,
                "local_user_id": data.local_user_id,
                "keka_employee_number": data.keka_employee_number,
                "last_synced_at": data.last_synced_at,
                "sync_status": data.sync_status,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "local_user_email": getattr(user, "email", None),
                "local_user_name": f"{first} {last}".strip() or None,
            }
        return data


class KekaEmployeeMappingListResponse(BaseModel):
    """Schema for list of Keka employee mappings with pagination."""

    total: int
    items: List[KekaEmployeeMappingResponse]

    model_config = ConfigDict(extra="ignore")


class KekaEmployeeMappingCreate(BaseModel):
    """Schema for manually creating a Keka employee to local user mapping."""

    keka_employee_id: str
    local_user_id: int
    keka_employee_number: Optional[str] = None
    sync_status: Optional[str] = "active"

    model_config = ConfigDict(extra="forbid")


class KekaEmployeeMappingFromPreview(BaseModel):
    """Schema for creating a mapping from preview selection."""

    keka_employee_id: str
    local_user_id: int
    keka_employee_number: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class KekaEmployeeMappingDeleteResponse(BaseModel):
    """Schema for delete mapping response."""

    keka_employee_id: str
    deleted: bool
    message: str

    model_config = ConfigDict(extra="ignore")


class KekaMappingPreviewItem(BaseModel):
    """Schema for a preview of an individual Keka employee mapping candidate."""

    keka_employee_id: str
    keka_employee_number: Optional[str] = None
    keka_name: Optional[str] = None
    keka_email: Optional[str] = None
    keka_department: Optional[str] = None
    keka_job_title: Optional[str] = None
    date_of_joining: Optional[str] = None
    employment_status: Optional[str] = None
    status: str  # 'mapped', 'local_match', 'unmapped', 'conflict'
    matched_local_user_id: Optional[int] = None
    matched_local_user_email: Optional[str] = None
    matched_local_user_name: Optional[str] = None
    matched_by: Optional[str] = None  # 'existing_mapping', 'email', 'employee_number', None
    reason: str

    model_config = ConfigDict(extra="ignore")


class KekaMappingPreviewResponse(BaseModel):
    """Schema for mapping preview summary and classified candidates."""

    total_keka_employees: int
    summary: Dict[str, int]
    items: List[KekaMappingPreviewItem]

    model_config = ConfigDict(extra="ignore")


class KekaLeaveSyncStatusResponse(BaseModel):
    """Schema for status of a local leave request synced to Keka."""

    local_leave_id: int
    user_id: int
    synced_to_keka: bool
    keka_leave_request_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    last_sync_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class KekaLeaveSyncActionResponse(BaseModel):
    """Schema for result of an on-demand sync push of a leave request to Keka."""

    success: bool
    synced: bool
    local_leave_id: int
    keka_leave_request_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    error: Optional[str] = None
    message: str

    model_config = ConfigDict(extra="ignore")


# =============================================================================
# CATEGORY 1 – HR CORE & EMPLOYEE LIFECYCLE SCHEMAS
# =============================================================================


class KekaEmployeeCreateRequest(BaseModel):
    """Schema for creating a new employee in Keka (POST /hris/employees)."""

    employeeNumber: Optional[str] = None
    displayName: Optional[str] = None
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    mobileNumber: Optional[str] = None
    gender: Optional[int] = None  # 0=Female, 1=Male, 2=Other, 3=Unknown
    dateOfBirth: Optional[str] = None
    dateJoined: Optional[str] = None
    department: Optional[str] = None
    businessUnit: Optional[str] = None
    jobTitle: Optional[str] = None
    secondaryJobTitle: Optional[str] = None
    location: Optional[str] = None
    legalEntity: Optional[str] = None
    nationality: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class KekaJobDetailsUpdateRequest(BaseModel):
    """Schema for updating employee job details (PUT /hris/employees/jobdetails)."""

    employeeId: Optional[str] = None
    user_id: Optional[int] = None
    employeeNumber: Optional[str] = None
    location: Optional[str] = None
    businessUnit: Optional[str] = None
    department: Optional[str] = None
    jobTitle: Optional[str] = None
    secondaryJobTitle: Optional[str] = None
    reportsToEmail: Optional[str] = None
    reportingManager: Optional[str] = None
    dottedLineManager: Optional[str] = None
    attendanceNumber: Optional[str] = None
    timeType: Optional[int] = None  # 0=FullTime, 1=PartTime, etc.
    attendanceCaptureScheme: Optional[str] = None
    expensePolicy: Optional[str] = None
    noticePeriod: Optional[str] = None
    holidayList: Optional[str] = None
    costCenter: Optional[str] = None
    leavePlan: Optional[str] = None
    payBand: Optional[str] = None
    payGrade: Optional[str] = None
    shiftPolicy: Optional[str] = None
    weeklyOffPolicy: Optional[str] = None
    attendancePenalisationPolicy: Optional[str] = None
    customFields: Optional[Dict[str, Any]] = None
    workerType: Optional[int] = None  # 0=Permanent, 1=Contract, etc.
    contingentTypeId: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_manager(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("reportsToEmail") and not data.get("reportingManager"):
                data["reportingManager"] = data["reportsToEmail"]
        return data


class KekaEmployeeExitRequest(BaseModel):
    """Schema for employee exit / deactivation (POST /hris/employees/{id}/exitrequest)."""

    exitType: Optional[int] = 0  # 0=Resignation, 1=Termination, etc.
    exitReason: Optional[str] = None
    resignationDate: Optional[str] = None
    lastWorkingDate: Optional[str] = None
    isOkToRehire: Optional[bool] = True
    comments: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


# =============================================================================
# CATEGORY 5 – ATTENDANCE TIME ENTRY SCHEMA
# =============================================================================


class KekaAddressSchema(BaseModel):
    """Address schema for attendance location."""

    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    countryCode: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class KekaAttendanceTimeEntryCreate(BaseModel):
    """Schema for recording employee attendance time entry (POST /attendance/employee/{id}/timeentry)."""

    timestamp: str  # ISO 8601 date-time string
    employeeIdentifier: Optional[str] = None
    user_id: Optional[int] = None
    note: Optional[str] = None
    punchStatus: int = 0  # 0=In, 1=Out
    attendanceLogSource: Optional[int] = 0
    manualClockinType: Optional[int] = 0
    premiseName: Optional[str] = None
    locationAddress: Optional[KekaAddressSchema] = None

    model_config = ConfigDict(extra="ignore")


# =============================================================================
# CATEGORY 12 & 13 – WORK FROM HOME & ON DUTY SCHEMAS
# =============================================================================


class KekaWFHCreateRequest(BaseModel):
    """Schema for submitting Work From Home request (POST /time/wfh)."""

    employeeId: str
    fromDate: str
    toDate: str
    fromSession: int = 0  # 0=Session 1, 1=Session 2
    toSession: int = 1    # 0=Session 1, 1=Session 2
    note: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class KekaODCreateRequest(BaseModel):
    """Schema for submitting On Duty request (POST /time/od)."""

    employeeId: str
    fromDate: str
    toDate: str
    fromSession: int = 0  # 0=Session 1, 1=Session 2
    toSession: int = 1    # 0=Session 1, 1=Session 2
    note: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

