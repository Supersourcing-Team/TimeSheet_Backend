# Keka UI to API Coverage Matrix

This document provides a strict, evidence-based audit of every Keka API implemented or referenced across the Timesheet HR Management System codebase.
In accordance with audit directives, TypeScript interfaces, RTK mutations, API helpers, backend routes, or services alone **do NOT** count as a UI. An actual, user-facing form, modal, or action button must exist in the frontend.

## Coverage Matrix

| Keka API | Backend Route | Frontend API Function | Actual UI | All Fields UI | Payload Complete | Status |
|---|---|---|---|---|---|---|
| **POST /hris/employees** (Create Employee) | `POST /api/v1/keka/employees` | `createKekaEmployeeApi` / `createKekaEmployee` | YES (`UserManagement.tsx` modal & `KekaManagement.tsx` modal) | YES (all 17 Keka fields) | YES | FULLY UI + API INTEGRATED |
| **PUT /hris/employees/jobdetails** (Update Job Details) | `PUT /api/v1/keka/employees/{employee_id}/job-details` (alias: `PUT /api/v1/keka/employees/jobdetails`) | `updateKekaJobDetails` | YES (`KekaManagement.tsx` Job Details Modal) | YES (jobTitle, secJobTitle, dept, BU, loc, reportsToEmail) | YES (non-Keka fields excluded) | FULLY UI + API INTEGRATED |
| **POST /hris/employees/{id}/exitrequest** (Exit Employee) | `POST /api/v1/keka/employees/{employee_id}/exit-request` (alias: `POST /api/v1/keka/employees/{employee_id}/exit`) | `createKekaExitRequest` | YES (`KekaManagement.tsx` Exit Modal) | YES (exitType, lastWorkingDate, resignationDate, exitReason, isOkToRehire, comments) | YES | FULLY UI + API INTEGRATED |
| **POST /attendance/employee/{id}/timeentry** (Log Punch) | `POST /api/v1/keka/attendance/employees/{employee_id}/timeentry` (alias: `POST /api/v1/keka/attendance/timeentry`) | `pushKekaTimeEntry` | YES (`KekaManagement.tsx` Log Punch Modal) | YES (employeeIdentifier, timestamp, punchStatus) | YES | FULLY UI + API INTEGRATED |
| **POST /time/leaverequests** (Create / Sync Leave) | `POST /api/v1/keka/leave-requests/{id}/sync` | `syncLeaveToKeka` | YES (`AdminLeaveApprovals.tsx` & `KekaManagement.tsx` retry queue) | YES (resolved from LeaveRequest entity & mapping) | YES | FULLY UI + API INTEGRATED |
| **POST /time/wfh** (Submit WFH Request) | `POST /api/v1/keka/wfh` | `createKekaWFH` | NO (mutation defined in `dataApi.ts`, no UI form exists) | NO | NO | API FUNCTION EXISTS BUT UI MISSING |
| **POST /time/od** (Submit On Duty Request) | `POST /api/v1/keka/od` | `createKekaOD` | NO (mutation defined in `dataApi.ts`, no UI form exists) | NO | NO | API FUNCTION EXISTS BUT UI MISSING |
| **POST /payroll/salary** (Salary / CTC API) | None | None | YES (CTC input in Add User UI) | NO (CTC only stored in local DB) | NO | UNSUPPORTED BY KEKA |
| **GET /hris/employees** (Get Employees) | `GET /api/v1/keka/employees` | `getKekaEmployees` / `getKekaMappingPreview` | YES (`KekaManagement.tsx` Mappings Table) | YES | YES | FULLY UI + API INTEGRATED |
| **GET /hris/employees/{id}** (Get Employee Profile) | `GET /api/v1/keka/employees/{employee_id}` | Direct API / Backend Service | NO (used internally for profile sync) | N/A | YES | READ ONLY |
| **GET /hris/departments** (Get Departments) | `GET /api/v1/keka/departments` | `getKekaDepartments` | YES (Department selector & sync in `UserManagement.tsx` & `KekaManagement.tsx`) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/departments** (Sync Depts) | `POST /api/v1/keka/sync/departments` | `syncKekaDepartments` | YES (`KekaManagement.tsx` "Sync Departments" button) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/employees** (Sync Employees) | `POST /api/v1/keka/sync/employees` | `syncKekaEmployees` | YES (`KekaManagement.tsx` "Sync Employees" button) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/holidays** (Sync Holidays) | `POST /api/v1/keka/sync/holidays` | `syncKekaHolidays` | YES (`KekaManagement.tsx` "Sync Holidays" button) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/weekly-off** (Sync Weekly Off) | `POST /api/v1/keka/sync/weekly-off` | Automated / Backend Task | NO DIRECT UI — SYSTEM SYNCHRONIZATION OPERATION | N/A | YES | SYNC ONLY |
| **GET /time/holidayscalendar** | `GET /api/v1/keka/holiday-calendars` | Service invocation | YES (via Sync Holidays UI) | YES | YES | SYNC ONLY |
| **GET /time/holidayscalendar/{id}/holidays** | `GET /api/v1/keka/holiday-calendars/{id}/holidays` | Service invocation | YES (via Sync Holidays UI) | YES | YES | SYNC ONLY |
| **GET /time/weeklyoffpolicies** | `GET /api/v1/keka/weekly-off-policies` | Service invocation | NO DIRECT UI — SYSTEM SYNCHRONIZATION OPERATION | N/A | YES | SYNC ONLY |
| **GET /time/attendance** | `GET /api/v1/keka/attendance` | `getKekaAttendance` | YES (`KekaManagement.tsx` Attendance tab) | YES | YES | FULLY UI + API INTEGRATED |
| **GET /time/attendance/exceptions** | `GET /api/v1/keka/attendance/exceptions` | `getKekaAttendanceExceptions` | YES (`KekaManagement.tsx` Exceptions tab) | YES | YES | FULLY UI + API INTEGRATED |
| **GET /time/leavetypes** | `GET /api/v1/keka/leave-types` | `getKekaLeaveTypes` | YES (`KekaManagement.tsx` Leave Types Mapping tab) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/leave-types** | `POST /api/v1/keka/sync/leave-types` | `syncLeaveTypes` | YES (`KekaManagement.tsx` "Sync Policies" button) | YES | YES | FULLY UI + API INTEGRATED |
| **GET /time/leavebalance** | `GET /api/v1/keka/leave-balances` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/leaveplans** | `GET /api/v1/keka/leave-plans` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/leaverequests** | `GET /api/v1/keka/leave-requests` | Backend Service / Query | YES (synced into `leave_requests` table) | YES | YES | FULLY UI + API INTEGRATED |
| **POST /api/v1/keka/sync/leaves/statuses** | `POST /api/v1/keka/sync/leaves/statuses` | Backend Scheduled Job / Sync API | NO DIRECT UI — SYSTEM SYNCHRONIZATION OPERATION | N/A | YES | SYNC ONLY |
| **GET /hris/employees/updatefields** | `GET /api/v1/keka/employees/updatefields` | `getKekaUpdateFields` | YES (called in `KekaManagement.tsx`, but form fields are statically structured) | YES | YES | READ ONLY |
| **GET /hris/jobtitles** | `GET /api/v1/keka/job-titles` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/locations** | `GET /api/v1/keka/locations` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/groups** | `GET /api/v1/keka/groups` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/grouptypes** | `GET /api/v1/keka/group-types` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/currencies** | `GET /api/v1/keka/currencies` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/noticeperiods** | `GET /api/v1/keka/notice-periods` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/exitreasons** | `GET /api/v1/keka/exit-reasons` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/contingenttypes** | `GET /api/v1/keka/contingent-types` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/documents/types** | `GET /api/v1/keka/documents/types` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/employees/{id}/documents** | `GET /api/v1/keka/employees/{employee_id}/documents` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /hris/employees/{id}/documents/{docId}/attachment** | `GET /api/v1/keka/employees/{employee_id}/documents/{doc_id}/attachment` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/shiftpolicies** | `GET /api/v1/keka/shift-policies` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/capturescheme** | `GET /api/v1/keka/capture-scheme` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/regularisationrequests** | `GET /api/v1/keka/regularisation-requests` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/penalisationpolicies** | `GET /api/v1/keka/penalisation-policies` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/wfh** | `GET /api/v1/keka/wfh` | Backend Service / Query | NO | N/A | YES | READ ONLY |
| **GET /time/od** | `GET /api/v1/keka/od` | Backend Service / Query | NO | N/A | YES | READ ONLY |
