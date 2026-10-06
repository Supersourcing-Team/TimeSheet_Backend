# KEKA API FUNCTIONALITY MATRIX
**Employee Timesheet & HR Management System**
*Source of Truth: Official Keka Developer Documentation (https://developers.keka.com/)*
*Audit Timestamp: 2026-10-06*

---

## 1. Executive Summary Table

| Category | Total APIs Audited | Fully Functional (End-to-End) | Read-Only | Unsupported by Keka v1 | Needs Fix |
|:---|:---:|:---:|:---:|:---:|:---:|
| **A. Employee Management** | 8 | 4 (Create, Update Job, Exit, Sync) | 4 (Get, GetAll, GetById, UpdateFields) | 0 | 0 |
| **B. Department / Organization** | 2 | 1 (Sync) | 1 (Get) | 0 | 0 |
| **C. Leave Management** | 6 | 2 (Create/Sync, Retry) | 3 (Types, Balances, Requests) | 1 (Cancel) | 0 |
| **D. Attendance & Time Entry** | 4 | 2 (Time Entry, Push Attendance) | 2 (Get Attendance, Schemes) | 0 | 0 |
| **E. Holidays** | 2 | 1 (Sync) | 1 (Get) | 0 | 0 |
| **F. Weekly Off** | 1 | 0 | 1 (Get) | 0 | 0 |
| **G. Work From Home (WFH)** | 2 | 1 (Create WFH) | 1 (Get WFH) | 0 | 0 |
| **H. On Duty (OD)** | 2 | 1 (Create OD) | 1 (Get OD) | 0 | 0 |
| **I. Shift Policies** | 1 | 0 | 1 (Get) | 0 | 0 |
| **J. Regularization** | 1 | 0 | 1 (Get) | 0 | 0 |
| **K. Documents** | 2 | 0 | 2 (Get Documents, Get Types) | 0 | 0 |
| **L. System / Diagnostics** | 2 | 2 (Status, Test Connection) | 0 | 0 | 0 |
| **TOTAL** | **33** | **14** | **18** | **1** | **0** |

---

## 2. Complete API Functionality Matrix

| API Name | Method | My Endpoint | Keka Endpoint | Request Fields Complete | Required Fields | Optional Fields | Correct Mapping | DB Integration | Response Handling | Error Handling | Tests | Status |
|:---|:---:|:---|:---|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Create Employee** | `POST` | `/api/v1/keka/employees` | `/hris/employees` | **Yes (17/17)** | `employeeNumber`, `firstName`, `lastName`, `email`, `dateJoined` | `displayName`, `middleName`, `mobileNumber`, `gender`, `dateOfBirth`, `department`, `businessUnit`, `jobTitle`, `secondaryJobTitle`, `location`, `legalEntity`, `nationality` | **Yes** (Local User $\leftrightarrow$ Keka UUID) | **Yes** (Creates `users`, inserts `keka_employee_mappings`) | **Yes** (Extracts `StringResponse.data` UUID) | **Yes** (Rollback safe, reports sync failure) | `test_create_employee_flow_complete_success` | **FULLY FUNCTIONAL** |
| **Get Employees (Paged)** | `GET` | `/api/v1/keka/employees` | `/hris/employees` | **Yes** | None (Params: `page`, `page_size`) | `pageNumber`, `pageSize` | N/A | No (Direct fetch) | **Yes** (Unpacks `PagedResponse`) | **Yes** (401/403/500 handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get All Employees** | `GET` | `/api/v1/keka/employees/all` | `/hris/employees/all` | **Yes** | None | `lastModified` | N/A | No (Direct fetch) | **Yes** (Unpacks `Response`) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get Employee By ID** | `GET` | `/api/v1/keka/employees/{id}` | `/hris/employees/{id}` | **Yes** | `id` (Local ID or Keka UUID resolved) | None | **Yes** (Maps local user ID to Keka UUID) | No (Direct fetch) | **Yes** (Unpacks single employee object) | **Yes** (404 handled) | `test_keka_extended.py` | **READ ONLY** |
| **Update Job Details** | `PUT` | `/api/v1/keka/employees/jobdetails` | `/hris/employees/jobdetails?employeeId={uuid}` | **Yes (6/6)** | `employeeId` (Query Param) | `jobTitle`, `secondaryJobTitle`, `department`, `businessUnit`, `location`, `reportsToEmail` | **Yes** (Resolves local user ID to Keka UUID) | **Yes** (Updates local `users` title/dept if matching) | **Yes** (Verifies 200/204 status) | **Yes** (404 mapping, Keka validation error) | `test_update_job_details_flow_success` | **FULLY FUNCTIONAL** |
| **Employee Exit Request** | `POST` | `/api/v1/keka/employees/{id}/exit` | `/hris/employees/{id}/exitrequest` | **Yes (6/6)** | `id`, `exitType`, `lastWorkingDate` | `exitReason`, `resignationDate`, `isOkToRehire`, `comments` | **Yes** (Resolves local user ID to Keka UUID) | **Yes** (Marks local user `status="Inactive"`) | **Yes** (Verifies 200 OK) | **Yes** (404 mapping, 400 validation error) | `test_employee_exit_flow_success` | **FULLY FUNCTIONAL** |
| **Employee Update Fields** | `GET` | `/api/v1/keka/employees/updatefields` | `/hris/employees/updatefields` | **Yes** | None | None | N/A | No (Metadata fetch) | **Yes** (Returns `profileFields` & `jobFields`) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Sync Employees** | `POST` | `/api/v1/keka/sync/employees` | `/hris/employees/all` | **Yes** | None | None | **Yes** (Bi-directional resolution) | **Yes** (Inserts/updates `users` & `keka_employee_mappings`) | **Yes** (Tracks created, updated, skipped) | **Yes** (Transaction safe) | `test_keka_business_flow.py` | **FULLY FUNCTIONAL** |
| **Get Departments** | `GET` | `/api/v1/keka/departments` | `/hris/departments` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks list) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Sync Departments** | `POST` | `/api/v1/keka/sync/departments` | `/hris/departments` | **Yes** | None | None | **Yes** (Department Name matching) | **Yes** (Inserts into `departments` table) | **Yes** (Tracks created/updated) | **Yes** (Transaction safe) | `test_keka_business_flow.py` | **FULLY FUNCTIONAL** |
| **Get Leave Types** | `GET` | `/api/v1/keka/leave/types` | `/time/leavetypes` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks list) | **Yes** (Handled) | `test_keka_leave.py` | **READ ONLY** |
| **Get Leave Balances** | `GET` | `/api/v1/keka/leave/balances` | `/time/leavebalance` | **Yes** | None | `employeeId` (Resolved from local user) | **Yes** (Translates local user ID $\to$ Keka UUID) | No (Direct fetch) | **Yes** (Unpacks balance breakdown) | **Yes** (Handled) | `test_keka_leave.py` | **READ ONLY** |
| **Get Leave Requests** | `GET` | `/api/v1/keka/leave/requests` | `/time/leaverequests` | **Yes** | None | `from`, `to`, `employeeIds` | **Yes** (Translates local IDs $\to$ Keka UUIDs) | No (Direct fetch) | **Yes** (Unpacks request list) | **Yes** (Handled) | `test_keka_leave.py` | **READ ONLY** |
| **Apply / Create Leave** | `POST` | `/api/v1/keka/leave/requests` | `/time/leaverequests` | **Yes (9/9)** | `employeeId`, `requestedBy`, `fromDate`, `toDate`, `leaveTypeId` | `reason`, `fromSession`, `toSession`, `note` | **Yes** (Translates local user ID to Keka UUID) | **Yes** (Creates/updates `leave_requests` & sync audit) | **Yes** (Extracts Keka request identifier) | **Yes** (Records `sync_status="FAILED"`, error details) | `test_sync_leave_to_keka_success` | **FULLY FUNCTIONAL** |
| **Leave Sync Retry** | `POST` | `/api/v1/keka/leave/{id}/sync` | `/time/leaverequests` | **Yes** | `leave_id` (Local ID) | None | **Yes** (Looks up mapping for leave's user) | **Yes** (Updates `keka_sync_status`, `synced_at`) | **Yes** (Records response) | **Yes** (Retries on transient errors) | `test_keka_leave.py` | **FULLY FUNCTIONAL** |
| **Cancel Leave Request** | `POST` | `/api/v1/keka/leave/{id}/cancel` | N/A | **N/A** | N/A | N/A | N/A | Local DB only | **N/A** | Explicit 501 / Unsupported error | `test_keka_leave.py` | **UNSUPPORTED BY KEKA** |
| **Get Unsynced Leaves** | `GET` | `/api/v1/keka/leave/unsynced` | N/A | **Yes** | None | None | N/A | **Yes** (Queries `leave_requests` where status != SYNCED) | **Yes** (Returns queue) | **Yes** (Handled) | `test_keka_leave.py` | **READ ONLY** |
| **Get Attendance** | `GET` | `/api/v1/keka/attendance` | `/attendance` | **Yes** | None | `from`, `to`, `employeeIds` | **Yes** (Translates local IDs $\to$ Keka UUIDs) | No (Direct fetch) | **Yes** (Unpacks records) | **Yes** (Handled) | `test_keka_attendance.py` | **READ ONLY** |
| **Push Time Entry (Punch)** | `POST` | `/api/v1/keka/attendance/timeentry` | `/attendance/employee/{routeEmployeeId}/timeentry` | **Yes (3/3)** | `timestamp`, `employeeIdentifier` | `punchStatus` (0-5, 99) | **Yes** (Resolves local user ID to Keka UUID/Number) | **Yes** (Logs sync in audit log) | **Yes** (Verifies 200 OK) | **Yes** (404 mapping, payload validation) | `test_push_attendance_time_entry_success` | **FULLY FUNCTIONAL** |
| **Push Attendance (Range)** | `POST` | `/api/v1/keka/attendance/push` | `/attendance/employee/{routeEmployeeId}/timeentry` | **Yes** | `user_id`, `date` | `clock_in`, `clock_out` | **Yes** (Translates local user ID $\to$ Keka Identifier) | **Yes** (Audits clock-in/out timestamps) | **Yes** (Verifies punch responses) | **Yes** (Captures failed punches) | `test_push_attendance_missing_mapping_fails` | **FULLY FUNCTIONAL** |
| **Get Attendance Schemes** | `GET` | `/api/v1/keka/attendance/schemes` | `/attendance/schemes` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks schemes) | **Yes** (Handled) | `test_keka_attendance.py` | **READ ONLY** |
| **Get Holidays** | `GET` | `/api/v1/keka/holidays` | `/time/holidays` | **Yes** | None | `year` | N/A | No (Direct fetch) | **Yes** (Unpacks holidays) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Sync Holidays** | `POST` | `/api/v1/keka/sync/holidays` | `/time/holidays` | **Yes** | None | None | **Yes** (Maps to local `WorkingCalendar`) | **Yes** (Inserts/updates `working_calendar` table) | **Yes** (Tracks created/updated) | **Yes** (Transaction safe) | `test_keka_business_flow.py` | **FULLY FUNCTIONAL** |
| **Get Weekly Off Policies** | `GET` | `/api/v1/keka/weekly-off` | `/time/weeklyoff` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks policies) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get WFH Requests** | `GET` | `/api/v1/keka/wfh` | `/time/wfh` | **Yes** | None | `from`, `to`, `employeeIds` | **Yes** (Translates local user IDs) | No (Direct fetch) | **Yes** (Unpacks WFH records) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Create WFH Request** | `POST` | `/api/v1/keka/wfh` | `/time/wfh` | **Yes (6/6)** | `employeeId`, `fromDate`, `toDate` | `fromSession`, `toSession`, `note` | **Yes** (Translates local user ID to Keka UUID) | **Yes** (Audits request in system) | **Yes** (Verifies 200 OK) | **Yes** (404 mapping, 400 validation error) | `test_create_wfh_flow_success` | **FULLY FUNCTIONAL** |
| **Get OD Requests** | `GET` | `/api/v1/keka/od` | `/time/od` | **Yes** | None | `from`, `to`, `employeeIds` | **Yes** (Translates local user IDs) | No (Direct fetch) | **Yes** (Unpacks OD records) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Create OD Request** | `POST` | `/api/v1/keka/od` | `/time/od` | **Yes (6/6)** | `employeeId`, `fromDate`, `toDate` | `fromSession`, `toSession`, `note` | **Yes** (Translates local user ID to Keka UUID) | **Yes** (Audits request in system) | **Yes** (Verifies 200 OK) | **Yes** (404 mapping, 400 validation error) | `test_create_od_flow_success` | **FULLY FUNCTIONAL** |
| **Get Shift Policies** | `GET` | `/api/v1/keka/shifts` | `/time/shifts` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks shift policies) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get Regularization Requests** | `GET` | `/api/v1/keka/regularization-requests` | `/attendance/regularizationrequests` | **Yes** | None | `from`, `to`, `employeeIds` | **Yes** (Translates local user IDs) | No (Direct fetch) | **Yes** (Unpacks requests) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get Employee Documents** | `GET` | `/api/v1/keka/employees/{id}/documents` | `/hris/employees/{id}/documents` | **Yes** | `id` (Resolved) | None | **Yes** (Maps local user ID to Keka UUID) | No (Direct fetch) | **Yes** (Unpacks documents) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Get Document Types** | `GET` | `/api/v1/keka/documents/types` | `/hris/employees/documents/types` | **Yes** | None | None | N/A | No (Direct fetch) | **Yes** (Unpacks types) | **Yes** (Handled) | `test_keka_extended.py` | **READ ONLY** |
| **Integration Status** | `GET` | `/api/v1/keka/status` | Internal / Keka Config | **Yes** | None | None | N/A | **Yes** (Queries mapping table count & sync timestamp) | **Yes** (Returns environment status) | **Yes** (Handled) | `test_keka_extended.py` | **FULLY FUNCTIONAL** |
| **Test Connection** | `GET` | `/api/v1/keka/test-connection` | `/hris/employees?pageSize=1` | **Yes** | None | None | N/A | No | **Yes** (Validates OAuth2 token & ping) | **Yes** (Reports auth/network failure) | `test_keka_extended.py` | **FULLY FUNCTIONAL** |

---

## 3. Explicit Verification: "If I call Add Employee with valid data, will a real employee be created in Keka?"

### Answer:
# **YES**

### The Exact 9-Step End-to-End Chain:
1. **Frontend / API Client**: Sends `POST /api/v1/keka/employees` with JSON payload matching `KekaEmployeeCreateRequest`.
2. **FastAPI Request Validation**: FastAPI validates request against `KekaEmployeeCreateRequest` (strict Pydantic schema containing only Keka-supported fields; rejects unsupported properties).
3. **Service Layer Execution**: `KekaService.create_employee_flow(db, request)` is invoked.
4. **KekaClient Invocation**: `KekaClient.create_employee(request.model_dump(exclude_none=True))` prepares the payload with exact official fields.
5. **Keka HTTP Call**: `POST https://{company_name}.keka.com/api/v1/hris/employees` with OAuth2 Bearer token in headers.
6. **Keka API Execution & Response**: Keka processes creation and returns HTTP 200 with `StringResponse` (`{"data": "8f8b8849-2e63-448a-a621-39655e81d77a", "succeeded": true, ...}`).
7. **Keka Employee ID Extraction**: `res.get("data")` extracts the new Keka UUID (`8f8b8849-2e63-448a-a621-39655e81d77a`).
8. **Local Database Synchronization**:
   - Creates or updates local `User` record (`users` table) with `first_name`, `last_name`, `email`, `department_id`, and `status="Active"`.
   - Creates or updates `KekaEmployeeMapping` (`keka_employee_mappings` table) binding `user_id` $\leftrightarrow$ `keka_employee_id` $\leftrightarrow$ `employee_number`.
   - Transaction committed atomically.
9. **Final API Response**: Returns HTTP 200 with structured JSON:
   ```json
   {
     "status": "success",
     "message": "Employee created successfully in Keka and synchronized locally.",
     "keka_employee_id": "8f8b8849-2e63-448a-a621-39655e81d77a",
     "user_id": 14,
     "employee_number": "EMP-9001",
     "email": "jane.doe@company.com",
     "synced_locally": true
   }
   ```

---

## 4. End-to-End Chain for All Other Supported WRITE Operations

### WRITE API 2: Update Employee Job Details
- **Endpoint**: `PUT /api/v1/keka/employees/jobdetails`
- **Chain**:
  1. `PUT /api/v1/keka/employees/jobdetails` receives `user_id` (or `employee_id`) and `KekaJobDetailsUpdateRequest`.
  2. Resolves local `user_id` to Keka UUID via `keka_employee_mappings`.
  3. `KekaService.update_employee_job_details_flow` calls `KekaClient.update_employee_job_details(keka_emp_id, payload)`.
  4. Keka executes `PUT /hris/employees/jobdetails?employeeId={uuid}`.
  5. Keka returns HTTP 200 `Response`.
  6. Service updates local `User` record (job title and department if changed) in the local database.
  7. Returns `{ "status": "success", "message": "Employee job details updated...", "user_id": 14, "keka_employee_id": "{uuid}" }`.

### WRITE API 3: Employee Exit Request
- **Endpoint**: `POST /api/v1/keka/employees/{id}/exit`
- **Chain**:
  1. `POST /api/v1/keka/employees/{id}/exit` receives employee identifier and `KekaEmployeeExitRequest`.
  2. Resolves local user ID to Keka UUID via `keka_employee_mappings`.
  3. `KekaService.create_employee_exit_flow` calls `KekaClient.create_employee_exit_request(keka_emp_id, payload)`.
  4. Keka executes `POST /hris/employees/{id}/exitrequest`.
  5. Keka returns HTTP 200 `Response`.
  6. Service updates local `User` status to `"Inactive"` in the local database.
  7. Returns `{ "status": "success", "message": "Employee exit request submitted...", "user_id": 14, "keka_employee_id": "{uuid}" }`.

### WRITE API 4: Create / Push Attendance Time Entry (Punch)
- **Endpoint**: `POST /api/v1/keka/attendance/timeentry`
- **Chain**:
  1. `POST /api/v1/keka/attendance/timeentry` receives punch request (`user_id`, `timestamp`, `punch_status`).
  2. Resolves local `user_id` to Keka UUID / employee number via `keka_employee_mappings`.
  3. `KekaAttendanceService.push_single_time_entry` calls `KekaClient.log_attendance_time_entry(keka_emp_id, payload)`.
  4. Keka executes `POST /attendance/employee/{routeEmployeeId}/timeentry`.
  5. Keka returns HTTP 200 `Response`.
  6. Response is audited in local attendance sync audit.
  7. Returns `{ "status": "success", "message": "Time entry pushed to Keka successfully.", ... }`.

### WRITE API 5: Apply / Sync Leave Request
- **Endpoint**: `POST /api/v1/keka/leave/requests` & Local Leave Creation Integration
- **Chain**:
  1. `POST /api/v1/keka/leave/requests` (or standard `POST /api/v1/leave-requests/` when sync is enabled) receives leave details.
  2. Resolves local user ID to Keka UUID via `keka_employee_mappings`.
  3. `KekaLeaveService.sync_leave_to_keka` calls `KekaClient.create_leave_request(payload)`.
  4. Keka executes `POST /time/leaverequests`.
  5. Keka returns HTTP 200 with created leave request details / identifier.
  6. Service updates local `LeaveRequest` record with `keka_leave_id`, `keka_sync_status="SYNCED"`, and `synced_at`.
  7. Returns success response with local ID and Keka Leave ID.

### WRITE API 6: Create Work From Home (WFH) Request
- **Endpoint**: `POST /api/v1/keka/wfh`
- **Chain**:
  1. `POST /api/v1/keka/wfh` receives `user_id`, `fromDate`, `toDate`, `fromSession`, `toSession`, `note`.
  2. Resolves local user ID to Keka UUID via `keka_employee_mappings`.
  3. `KekaService.create_wfh_flow` calls `KekaClient.create_wfh_request(payload)`.
  4. Keka executes `POST /time/wfh`.
  5. Keka returns HTTP 200 `Response`.
  6. Response confirmed and audited.
  7. Returns `{ "status": "success", "message": "WFH request created...", "user_id": 14, "keka_employee_id": "{uuid}" }`.

### WRITE API 7: Create On Duty (OD) Request
- **Endpoint**: `POST /api/v1/keka/od`
- **Chain**:
  1. `POST /api/v1/keka/od` receives `user_id`, `fromDate`, `toDate`, `fromSession`, `toSession`, `note`.
  2. Resolves local user ID to Keka UUID via `keka_employee_mappings`.
  3. `KekaService.create_od_flow` calls `KekaClient.create_od_request(payload)`.
  4. Keka executes `POST /time/od`.
  5. Keka returns HTTP 200 `Response`.
  6. Response confirmed and audited.
  7. Returns `{ "status": "success", "message": "OD request created...", "user_id": 14, "keka_employee_id": "{uuid}" }`.
