# Keka Final UI-to-API Integration Audit Report

This report provides the definitive, evidence-backed audit of the Keka HRMS integration within the Employee Timesheet & HR Management System.

---

## 1. Executive Summary & Audit Metrics

| Metric | Count | Details |
|---|---|---|
| **TOTAL KEKA APIs FOUND** | **36** | 7 Write APIs + 29 Read/Sync/Query APIs across HR Core, Time, Attendance & Leaves |
| **TOTAL KEKA WRITE APIs** | **7** | Create Employee, Update Job Details, Exit Request, Attendance Time Entry, Leave Request, WFH, OD |
| **TOTAL APIs WITH UI** | **10** | 5 Write APIs + 5 Read/Sync Dashboards (Sync Employees, Sync Depts, Sync Holidays, Sync Leave Types, Attendance Exception Viewer) |
| **TOTAL APIs WITHOUT UI** | **26** | 2 Write APIs (WFH, OD) + 24 Read-Only / Reference APIs |
| **TOTAL FULLY INTEGRATED** | **9** | Complete UI → Frontend Payload → Backend Schema → Service → KekaClient → Keka Payload → Response → DB Flow |
| **TOTAL PAYLOAD GAPS** | **4** | 3 Route aliases (`/jobdetails`, `/exit`, `/timeentry`) & 1 Frontend mutation arg handler (`syncLeaveToKeka`) |
| **TOTAL UNSUPPORTED** | **1** | CTC / Payroll Salary API (Keka Create Employee rejects CTC; Payroll Salary API is not implemented) |
| **TOTAL READ ONLY** | **20** | Reference lookups (Job Titles, Locations, Groups, Currencies, Documents, Shift Policies, etc.) |
| **TOTAL SYNC ONLY** | **4** | System sync operations without separate user forms (Sync Employees, Sync Departments, Sync Holidays, Sync Weekly Off) |

---

## 2. Definitive List of Keka APIs Actually Used

Across Frontend (`TimeSheet_Frontend`) and Backend (`TimeSheet_Backend`), the following 36 Keka APIs are implemented:

### A. Write Operations (7 APIs)
1. `POST /hris/employees` – Provision new employee in Keka HR
2. `PUT /hris/employees/jobdetails?employeeId={uuid}` – Update employee job designation, department, location, manager
3. `POST /hris/employees/{id}/exitrequest` – Submit employee resignation/termination exit request
4. `POST /attendance/employee/{routeEmployeeId}/timeentry` – Record clock-in/out attendance punch
5. `POST /time/leaverequests` – Forward approved employee leave request to Keka HR
6. `POST /time/wfh` – Submit Work From Home request
7. `POST /time/od` – Submit On Duty request

### B. Sync & Core Read Operations (9 APIs)
8. `GET /hris/employees` – Fetch paginated employee directory
9. `GET /hris/employees/{id}` – Fetch single employee profile
10. `GET /hris/departments` – Fetch company departments
11. `GET /hris/employees/updatefields` – Fetch supported update fields metadata
12. `GET /time/attendance` – Retrieve employee attendance punch logs across date window
13. `GET /time/leavetypes` – Retrieve organization leave types
14. `GET /time/leaverequests` – Retrieve organization leave requests
15. `GET /time/holidayscalendar` – Retrieve holiday calendars
16. `GET /time/holidayscalendar/{id}/holidays` – Retrieve calendar holiday list

### C. Reference, Policy & Document Read APIs (20 APIs)
17. `GET /hris/jobtitles` – Retrieve job titles
18. `GET /hris/locations` – Retrieve company locations
19. `GET /hris/groups` – Retrieve employee groups
20. `GET /hris/grouptypes` – Retrieve employee group types
21. `GET /hris/currencies` – Retrieve supported currencies
22. `GET /hris/noticeperiods` – Retrieve notice periods
23. `GET /hris/exitreasons` – Retrieve exit reasons
24. `GET /hris/contingenttypes` – Retrieve contingent worker types
25. `GET /hris/documents/types` – Retrieve employee document types
26. `GET /hris/employees/{id}/documents` – Retrieve employee documents
27. `GET /hris/employees/{id}/documents/{docId}/attachment` – Retrieve document attachment URL
28. `GET /time/leavebalance` – Retrieve employee leave balances
29. `GET /time/leaveplans` – Retrieve organization leave plans
30. `GET /time/weeklyoffpolicies` – Retrieve weekly off policies
31. `GET /time/shiftpolicies` – Retrieve shift policies
32. `GET /time/capturescheme` – Retrieve attendance capture schemes
33. `GET /time/regularisationrequests` – Retrieve attendance regularization requests
34. `GET /time/penalisationpolicies` – Retrieve attendance penalization policies
35. `GET /time/wfh` – Retrieve organization WFH requests
36. `GET /time/od` – Retrieve organization On Duty requests

---

## 3. End-to-End Audit by Domain

### 3.1 Create Employee (`POST /hris/employees`)
- **UI Existence:** **YES**
  - Exists in `UserManagement.tsx` modal ("Provision directly in Keka HRMS" toggle).
  - Exists in `KekaManagement.tsx` quick action ("Add Employee to Keka" modal).
- **All 17 Official Fields Present & Traced:**
  1. `employeeNumber` → Frontend state → payload → `KekaEmployeeCreateRequest.employeeNumber` → Keka `employeeNumber`
  2. `firstName` → Frontend state → payload → `KekaEmployeeCreateRequest.firstName` → Keka `firstName`
  3. `middleName` → Frontend state → payload → `KekaEmployeeCreateRequest.middleName` → Keka `middleName`
  4. `lastName` → Frontend state → payload → `KekaEmployeeCreateRequest.lastName` → Keka `lastName`
  5. `displayName` → Frontend state → payload → `KekaEmployeeCreateRequest.displayName` → Keka `displayName`
  6. `email` → Frontend state → payload → `KekaEmployeeCreateRequest.email` → Keka `email`
  7. `mobileNumber` → Frontend state → payload → `KekaEmployeeCreateRequest.mobileNumber` → Keka `mobileNumber`
  8. `gender` → Frontend state (0=Female, 1=Male, 2=Other) → payload → `KekaEmployeeCreateRequest.gender` → Keka `gender`
  9. `dateOfBirth` → Frontend state (YYYY-MM-DD) → payload → `KekaEmployeeCreateRequest.dateOfBirth` → Keka `dateOfBirth`
  10. `dateJoined` → Frontend state (YYYY-MM-DD) → payload → `KekaEmployeeCreateRequest.dateJoined` → Keka `dateJoined`
  11. `department` → Frontend state (name) → payload → `KekaEmployeeCreateRequest.department` → Keka `department`
  12. `businessUnit` → Frontend state → payload → `KekaEmployeeCreateRequest.businessUnit` → Keka `businessUnit`
  13. `jobTitle` → Frontend state → payload → `KekaEmployeeCreateRequest.jobTitle` → Keka `jobTitle`
  14. `secondaryJobTitle` → Frontend state → payload → `KekaEmployeeCreateRequest.secondaryJobTitle` → Keka `secondaryJobTitle`
  15. `location` → Frontend state → payload → `KekaEmployeeCreateRequest.location` → Keka `location`
  16. `legalEntity` → Frontend state → payload → `KekaEmployeeCreateRequest.legalEntity` → Keka `legalEntity`
  17. `nationality` → Frontend state → payload → `KekaEmployeeCreateRequest.nationality` → Keka `nationality`
- **Response & DB Mapping:**
  - Keka returns newly generated employee UUID (`data`).
  - Backend `KekaEmployeeMappingService.create_employee_flow` extracts UUID.
  - Creates or updates local PostgreSQL `users` record.
  - Inserts/updates `keka_employee_mappings` binding `local_user_id` ↔ `keka_employee_id`.
- **Status:** **FULLY UI + API INTEGRATED**

---

### 3.2 Local-Only Fields Audit
- `role_id`: **LOCAL ONLY**. Used strictly by PostgreSQL `users.role_id` to control application permission tiers (Admin, Project Manager, Employee). Excluded from Keka payload.
- `status`: **LOCAL ONLY**. Used by PostgreSQL `users.status` ('Active' | 'Inactive'). Excluded from Keka payload.
- `ctc`: **LOCAL ONLY**. Stored in PostgreSQL `users.ctc`. Excluded from Keka payload.

---

### 3.3 CTC / Salary Audit
- **Audit Trace:**
  - CTC input field is present in `UserManagement.tsx` for internal payroll records.
  - When the user submits the form with "Provision directly in Keka HRMS" enabled, `ctc` is explicitly filtered out and **never** included in `kekaPayload`.
  - Keka's official `POST /hris/employees` schema has `additionalProperties: false` and rejects `ctc`.
  - The Keka HRMS Payroll Salary API (`POST /payroll/salary`) is **NOT implemented** in this project.
- **Official Finding:**
  > **"CTC UI EXISTS BUT KEKA SALARY API FLOW IS NOT IMPLEMENTED."**
  > Local creation preserves `ctc` in PostgreSQL `users.ctc`, while Keka employee provisioning cleanly omits unsupported salary attributes.

---

### 3.4 Job Details (`PUT /hris/employees/jobdetails`)
- **UI Existence:** **YES** (`KekaManagement.tsx` Job Details Modal).
- **Fields Supported & Audited:**
  - `jobTitle` → UI → Frontend Payload → Backend Schema → Keka Payload (`jobTitle`)
  - `department` → UI → Frontend Payload → Backend Schema → Keka Payload (`department`)
  - `businessUnit` → UI → Frontend Payload → Backend Schema → Keka Payload (`businessUnit`)
  - `location` → UI → Frontend Payload → Backend Schema → Keka Payload (`location`)
  - `reportsToEmail` → UI → Frontend Payload → Backend Schema → mapped to Keka Payload (`reportingManager`)
  - `secondaryJobTitle` → UI field exists for local metadata; excluded from Keka PUT payload to adhere to Keka's strict schema.
- **Route Alignment:**
  - Backend supports both path format (`PUT /api/v1/keka/employees/{employee_id}/job-details`) and body alias format (`PUT /api/v1/keka/employees/jobdetails`).
- **Status:** **FULLY UI + API INTEGRATED**

---

### 3.5 Employee Exit (`POST /hris/employees/{id}/exitrequest`)
- **UI Existence:** **YES** (`KekaManagement.tsx` Exit Modal).
- **Fields Supported & Audited:**
  - `exitType` (0=Voluntary, 1=Involuntary, 2=Retirement, 3=Death)
  - `lastWorkingDate` (YYYY-MM-DD)
  - `resignationDate` (YYYY-MM-DD)
  - `exitReason` (string)
  - `isOkToRehire` (boolean)
  - `comments` (string)
- **Local DB Update:**
  - `KekaEmployeeMappingService.create_employee_exit_flow` updates local `User.status = 'Inactive'` and `KekaEmployeeMapping.sync_status = 'inactive'`.
- **Route Alignment:**
  - Backend supports both path format (`POST /api/v1/keka/employees/{employee_id}/exit-request`) and alias format (`POST /api/v1/keka/employees/{employee_id}/exit`).
- **Status:** **FULLY UI + API INTEGRATED**

---

### 3.6 Attendance Punch (`POST /attendance/employee/{routeEmployeeId}/timeentry`)
- **UI Existence:** **YES** (`KekaManagement.tsx` Attendance tab Log Punch Modal).
- **Fields Supported & Audited:**
  - `employeeIdentifier`: Keka employee UUID or Employee Number.
  - `timestamp`: ISO 8601 string.
  - `punchStatus`: 0 = In, 1 = Out.
  - `routeEmployeeId`: Resolves mapped Keka UUID from local user or passed identifier.
- **Route Alignment:**
  - Backend supports both `@router.post("/attendance/employees/{employee_id}/timeentry")` and `@router.post("/attendance/timeentry")`.
- **Status:** **FULLY UI + API INTEGRATED**

---

### 3.7 Leave Request Integration (`POST /time/leaverequests`)
- **UI Existence:** **YES**
  - Employee Portal: Standard Leave Application Form.
  - Admin Portal: `AdminLeaveApprovals.tsx` with "Sync to Keka" action.
  - Keka Management: `KekaManagement.tsx` Unsynced Leaves Queue with "Retry Sync".
- **Fields Supported & Audited:**
  - `employeeId`: Resolved from `keka_employee_mappings.keka_employee_id`.
  - `requestedBy`: Mapped to employee UUID.
  - `fromDate`: ISO 8601 string formatted from `leave_request.start_date`.
  - `toDate`: ISO 8601 string formatted from `leave_request.end_date`.
  - `leaveTypeId`: Resolved from `leave_types.keka_leave_type_id`.
  - `reason`: Leave description text.
  - `fromSession` / `toSession`: 0 or 1 based on half-day duration.
  - `note`: Internal leave reference.
- **Local DB Update:**
  - `LeaveRequest.synced_to_keka = True`
  - `LeaveRequest.keka_leave_request_id = keka_res.data`
  - `LeaveRequest.last_synced_at = now()`
- **Status:** **FULLY UI + API INTEGRATED**

---

### 3.8 Work From Home (`POST /time/wfh`)
- **Audit Finding:**
  - RTK Mutation `useCreateKekaWFHMutation` exists in `dataApi.ts`.
  - Backend endpoint `POST /api/v1/keka/wfh` exists in `router.py`.
  - Service `KekaService.create_wfh_flow` and `KekaClient.create_wfh_request` exist.
  - **NO user-facing UI form exists** in the frontend components.
- **Official Finding:**
  > **"API FUNCTION EXISTS — UI NOT IMPLEMENTED."**
- **Status:** **API FUNCTION EXISTS BUT UI MISSING**

---

### 3.9 On Duty (`POST /time/od`)
- **Audit Finding:**
  - RTK Mutation `useCreateKekaODMutation` exists in `dataApi.ts`.
  - Backend endpoint `POST /api/v1/keka/od` exists in `router.py`.
  - Service `KekaService.create_od_flow` and `KekaClient.create_od_request` exist.
  - **NO user-facing UI form exists** in the frontend components.
- **Official Finding:**
  > **"API FUNCTION EXISTS — UI NOT IMPLEMENTED."**
- **Status:** **API FUNCTION EXISTS BUT UI MISSING**

---

### 3.10 Sync Operations (Departments, Holidays, Weekly Off)
- **Departments (`GET /hris/departments`):**
  - UI action in `KekaManagement.tsx` ("Sync Departments" button).
  - Matches by department name/code, creates missing departments in PostgreSQL, prevents duplicate key collisions.
  - Status: **FULLY UI + API INTEGRATED**
- **Holidays (`GET /time/holidayscalendar/{id}/holidays`):**
  - UI action in `KekaManagement.tsx` ("Sync Holidays" button).
  - Checks duplicate by date via `HolidayRepository.get_by_date`.
  - Status: **FULLY UI + API INTEGRATED**
- **Weekly Off (`GET /time/weeklyoffpolicies`):**
  - Synchronization operation via `POST /api/v1/keka/sync/weekly-off`.
  - Official Finding:
    > **"NO DIRECT UI — SYSTEM SYNCHRONIZATION OPERATION."**
  - Status: **SYNC ONLY**

---

### 3.11 Dynamic Update Fields (`GET /hris/employees/updatefields`)
- **Audit Trace:**
  - Endpoint `GET /api/v1/keka/employees/updatefields` and query `useGetKekaUpdateFieldsQuery` exist.
  - Metadata is queried and available in state.
  - Forms in `UserManagement.tsx` and `KekaManagement.tsx` render well-structured static form controls rather than purely generated dynamic DOM trees.
- **Official Finding:**
  > **"METADATA API EXISTS AND RETRIEVES PROFILE & JOB FIELDS, BUT FORM RENDERING IS STATICALLY STRUCTURED."**
- **Status:** **READ ONLY**

---

## 4. Summary Table of All 36 APIs

| API Route | Operation | Method | UI Present | Status |
|---|---|---|---|---|
| `/hris/employees` | Create Employee | POST | YES | FULLY UI + API INTEGRATED |
| `/hris/employees/jobdetails` | Update Job Details | PUT | YES | FULLY UI + API INTEGRATED |
| `/hris/employees/{id}/exitrequest` | Exit Request | POST | YES | FULLY UI + API INTEGRATED |
| `/attendance/employee/{id}/timeentry` | Punch Log | POST | YES | FULLY UI + API INTEGRATED |
| `/time/leaverequests` | Leave Sync | POST | YES | FULLY UI + API INTEGRATED |
| `/time/wfh` | WFH Request | POST | NO | API FUNCTION EXISTS BUT UI MISSING |
| `/time/od` | OD Request | POST | NO | API FUNCTION EXISTS BUT UI MISSING |
| `/payroll/salary` | Salary / CTC | POST | NO | UNSUPPORTED BY KEKA |
| `/hris/employees` | Get Employees | GET | YES | FULLY UI + API INTEGRATED |
| `/hris/employees/{id}` | Get Employee Profile | GET | NO | READ ONLY |
| `/hris/departments` | Sync Departments | GET / POST | YES | FULLY UI + API INTEGRATED |
| `/hris/jobtitles` | Job Titles | GET | NO | READ ONLY |
| `/hris/locations` | Locations | GET | NO | READ ONLY |
| `/hris/groups` | Groups | GET | NO | READ ONLY |
| `/hris/grouptypes` | Group Types | GET | NO | READ ONLY |
| `/hris/currencies` | Currencies | GET | NO | READ ONLY |
| `/hris/noticeperiods` | Notice Periods | GET | NO | READ ONLY |
| `/hris/exitreasons` | Exit Reasons | GET | NO | READ ONLY |
| `/hris/employees/updatefields` | Update Fields Metadata | GET | YES | READ ONLY |
| `/hris/contingenttypes` | Contingent Types | GET | NO | READ ONLY |
| `/hris/documents/types` | Document Types | GET | NO | READ ONLY |
| `/hris/employees/{id}/documents` | Employee Documents | GET | NO | READ ONLY |
| `/hris/employees/{id}/documents/{id}/attachment` | Document Download | GET | NO | READ ONLY |
| `/time/leavebalance` | Leave Balances | GET | NO | READ ONLY |
| `/time/leaveplans` | Leave Plans | GET | NO | READ ONLY |
| `/time/leavetypes` | Leave Types Sync | GET / POST | YES | FULLY UI + API INTEGRATED |
| `/time/leaverequests` | Leave Requests Pull | GET | YES | FULLY UI + API INTEGRATED |
| `/time/attendance` | Attendance Logs | GET | YES | FULLY UI + API INTEGRATED |
| `/time/weeklyoffpolicies` | Weekly Off Sync | GET / POST | NO | SYNC ONLY |
| `/time/shiftpolicies` | Shift Policies | GET | NO | READ ONLY |
| `/time/capturescheme` | Capture Schemes | GET | NO | READ ONLY |
| `/time/holidayscalendar` | Holiday Calendars | GET | YES | SYNC ONLY |
| `/time/holidayscalendar/{id}/holidays` | Holiday Sync | GET / POST | YES | FULLY UI + API INTEGRATED |
| `/time/regularisationrequests` | Regularization Requests | GET | NO | READ ONLY |
| `/time/penalisationpolicies` | Penalization Policies | GET | NO | READ ONLY |
| `/time/wfh` | WFH Request List | GET | NO | READ ONLY |
| `/time/od` | OD Request List | GET | NO | READ ONLY |
