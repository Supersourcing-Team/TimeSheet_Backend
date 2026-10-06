# Keka Field Mapping Final Matrix

This document provides the exhaustive field-level mapping across all tiers:
**Official Keka Request Spec ↔ Frontend Form ↔ Frontend Payload ↔ Backend Schema ↔ Service Payload ↔ Actual Keka HTTP Payload**.

---

## 1. Create Employee (`POST /hris/employees`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /hris/employees` | `employeeNumber` | Employee ID (`employee_id` / `employeeNumber`) | `employeeNumber` | `employeeNumber` | `employeeNumber` | Optional (Generated if empty) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `firstName` | First Name * (`first_name` / `firstName`) | `firstName` | `firstName` | `firstName` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `middleName` | Middle Name (`middle_name` / `middleName`) | `middleName` | `middleName` | `middleName` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `lastName` | Last Name * (`last_name` / `lastName`) | `lastName` | `lastName` | `lastName` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `displayName` | Display Name (`display_name` / `displayName`) | `displayName` | `displayName` | `displayName` | Optional (Defaults to Full Name) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `email` | Email Address * (`email`) | `email` | `email` | `email` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `mobileNumber` | Mobile Number (`mobile_number` / `mobileNumber`) | `mobileNumber` | `mobileNumber` | `mobileNumber` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `gender` | Gender (`gender` select: 0, 1, 2) | `gender` (number) | `gender` (int) | `gender` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `dateOfBirth` | Date of Birth (`date_of_birth` / `dateOfBirth`) | `dateOfBirth` | `dateOfBirth` | `dateOfBirth` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `dateJoined` | Joining Date * (`joining_date` / `dateJoined`) | `dateJoined` | `dateJoined` | `dateJoined` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `department` | Department (`department_id` name / `department`) | `department` (string) | `department` | `department` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `businessUnit` | Business Unit (`business_unit` / `businessUnit`) | `businessUnit` | `businessUnit` | `businessUnit` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `jobTitle` | Job Title (`job_title` / `jobTitle`) | `jobTitle` | `jobTitle` | `jobTitle` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `secondaryJobTitle` | Secondary Job Title (`secondary_job_title` / `secondaryJobTitle`) | `secondaryJobTitle` | `secondaryJobTitle` | `secondaryJobTitle` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `location` | Location (`location`) | `location` | `location` | `location` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `legalEntity` | Legal Entity (`legal_entity` / `legalEntity`) | `legalEntity` | `legalEntity` | `legalEntity` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees` | `nationality` | Nationality (`nationality`) | `nationality` | `nationality` | `nationality` | Optional | FULLY UI + API INTEGRATED |
| **Local-Only** | `role_id` | Role Selection * | `role_id` (Local User table only) | None in Keka DTO | Excluded from Keka payload | Required for Local App | LOCAL ONLY |
| **Local-Only** | `status` | Status (Active / Inactive) | `status` (Local User table only) | None in Keka DTO | Excluded from Keka payload | Optional | LOCAL ONLY |
| **Local-Only** | `ctc` | CTC (Annual Salary in INR) | `ctc` (Local User table only) | None in Keka DTO | Excluded from Keka payload | Optional | LOCAL ONLY |

---

## 2. Update Employee Job Details (`PUT /hris/employees/jobdetails`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `PUT /hris/employees/jobdetails` | Query: `employeeId` | Row Keka ID | `employeeId` | `employee_id` / `employeeId` | Query Param `?employeeId=` | Required | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `jobTitle` | Job Title | `jobTitle` | `jobTitle` | `jobTitle` | Optional | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `secondaryJobTitle` | Secondary Job Title | `secondaryJobTitle` | `secondaryJobTitle` | Excluded from PUT (Unsupported by Keka PUT) | Optional | UI EXISTS (Excluded from Keka PUT) |
| `PUT /hris/employees/jobdetails` | `department` | Department | `department` | `department` | `department` | Optional | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `businessUnit` | Business Unit | `businessUnit` | `businessUnit` | `businessUnit` | Optional | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `location` | Location | `location` | `location` | `location` | Optional | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `reportingManager` | Reports To Email | `reportsToEmail` | `reportsToEmail` / `reportingManager` | `reportingManager` | Optional | FULLY UI + API INTEGRATED |
| `PUT /hris/employees/jobdetails` | `employeeNumber` | Not in Quick Modal | N/A | `employeeNumber` | `employeeNumber` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `timeType` | Not in Quick Modal | N/A | `timeType` | `timeType` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `attendanceCaptureScheme` | Not in Quick Modal | N/A | `attendanceCaptureScheme` | `attendanceCaptureScheme` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `expensePolicy` | Not in Quick Modal | N/A | `expensePolicy` | `expensePolicy` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `noticePeriod` | Not in Quick Modal | N/A | `noticePeriod` | `noticePeriod` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `holidayList` | Not in Quick Modal | N/A | `holidayList` | `holidayList` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `costCenter` | Not in Quick Modal | N/A | `costCenter` | `costCenter` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `leavePlan` | Not in Quick Modal | N/A | `leavePlan` | `leavePlan` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `payBand` | Not in Quick Modal | N/A | `payBand` | `payBand` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `payGrade` | Not in Quick Modal | N/A | `payGrade` | `payGrade` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `shiftPolicy` | Not in Quick Modal | N/A | `shiftPolicy` | `shiftPolicy` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `weeklyOffPolicy` | Not in Quick Modal | N/A | `weeklyOffPolicy` | `weeklyOffPolicy` | Optional | API + BACKEND ONLY |
| `PUT /hris/employees/jobdetails` | `workerType` | Not in Quick Modal | N/A | `workerType` | `workerType` | Optional | API + BACKEND ONLY |

---

## 3. Employee Exit Request (`POST /hris/employees/{id}/exitrequest`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /hris/employees/{id}/exitrequest` | Path: `id` | Row Keka ID | `employee_id` | `employee_id` | Path URL `{employee_id}` | Required | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `exitType` | Exit Type (Select: 0=Voluntary, 1=Involuntary) | `exitType` (number) | `exitType` (int) | `exitType` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `lastWorkingDate` | Last Working Date * (YYYY-MM-DD) | `lastWorkingDate` | `lastWorkingDate` | `lastWorkingDate` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `resignationDate` | Resignation Date (YYYY-MM-DD) | `resignationDate` | `resignationDate` | `resignationDate` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `exitReason` | Exit Reason | `exitReason` | `exitReason` | `exitReason` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `isOkToRehire` | Eligible for Rehire (Checkbox) | `isOkToRehire` (bool) | `isOkToRehire` (bool) | `isOkToRehire` | Optional | FULLY UI + API INTEGRATED |
| `POST /hris/employees/{id}/exitrequest` | `comments` | Comments / Offboarding Notes | `comments` | `comments` | `comments` | Optional | FULLY UI + API INTEGRATED |

---

## 4. Attendance Time Entry (`POST /attendance/employee/{id}/timeentry`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /attendance/employee/{id}/timeentry` | Path: `routeEmployeeId` | Employee Identifier (UUID or Number) | `employeeIdentifier` | `employee_id` / `employeeIdentifier` | Path URL `{employee_id}` | Required | FULLY UI + API INTEGRATED |
| `POST /attendance/employee/{id}/timeentry` | `timestamp` | Timestamp * (ISO string) | `timestamp` | `timestamp` | `timestamp` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /attendance/employee/{id}/timeentry` | `punchStatus` | Punch Status (0=In, 1=Out) | `punchStatus` (number) | `punchStatus` (int) | `punchStatus` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /attendance/employee/{id}/timeentry` | `employeeIdentifier` | Employee Identifier | `employeeIdentifier` | `employeeIdentifier` | `employeeIdentifier` | Optional | FULLY UI + API INTEGRATED |
| `POST /attendance/employee/{id}/timeentry` | `note` | Auto-generated note | `note` | `note` | `note` | Optional | FULLY UI + API INTEGRATED |
| `POST /attendance/employee/{id}/timeentry` | `locationAddress` | Not in Quick Modal | N/A | `locationAddress` | `locationAddress` | Optional | API + BACKEND ONLY |

---

## 5. Leave Request (`POST /time/leaverequests`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /time/leaverequests` | `employeeId` | Local Leave Request User | Auto-resolved from `keka_employee_mappings` | `keka_employee_id` | `employeeId` | Required | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `requestedBy` | Local Leave Request User | Auto-resolved from `keka_employee_mappings` | `keka_employee_id` | `requestedBy` | Required | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `fromDate` | Leave Start Date | `leave_request.start_date` | `start_date` | `fromDate` (ISO format) | Required (*) | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `toDate` | Leave End Date | `leave_request.end_date` | `end_date` | `toDate` (ISO format) | Required (*) | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `fromSession` | Half Day selection | Derived from `leave_duration_type` | `from_session` (0 or 1) | `fromSession` | Required | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `toSession` | Half Day selection | Derived from `leave_duration_type` | `to_session` (0 or 1) | `toSession` | Required | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `leaveTypeId` | Leave Type dropdown | Mapped via `leave_types.keka_leave_type_id` | `keka_leave_type_id` | `leaveTypeId` | Required (*) | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `reason` | Reason textarea | `leave_request.reason` | `reason` | `reason` | Optional | FULLY UI + API INTEGRATED |
| `POST /time/leaverequests` | `note` | Portal metadata | `Local Leave ID: {id}` | `note` | `note` | Optional | FULLY UI + API INTEGRATED |

---

## 6. Work From Home (`POST /time/wfh`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /time/wfh` | `employeeId` | None (No UI Form) | `employeeId` (in RTK payload) | `employeeId` | `employeeId` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/wfh` | `fromDate` | None (No UI Form) | `fromDate` | `fromDate` | `fromDate` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/wfh` | `toDate` | None (No UI Form) | `toDate` | `toDate` | `toDate` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/wfh` | `fromSession` | None (No UI Form) | `fromSession` | `fromSession` | `fromSession` | Optional | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/wfh` | `toSession` | None (No UI Form) | `toSession` | `toSession` | `toSession` | Optional | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/wfh` | `note` | None (No UI Form) | `note` | `note` | `note` | Optional | API FUNCTION EXISTS BUT UI MISSING |

---

## 7. On Duty (`POST /time/od`)

| API | Keka Field | UI Field | Frontend Payload | Backend Field | Keka Payload | Required/Optional | Status |
|---|---|---|---|---|---|---|---|
| `POST /time/od` | `employeeId` | None (No UI Form) | `employeeId` (in RTK payload) | `employeeId` | `employeeId` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/od` | `fromDate` | None (No UI Form) | `fromDate` | `fromDate` | `fromDate` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/od` | `toDate` | None (No UI Form) | `toDate` | `toDate` | `toDate` | Required | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/od` | `fromSession` | None (No UI Form) | `fromSession` | `fromSession` | `fromSession` | Optional | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/od` | `toSession` | None (No UI Form) | `toSession` | `toSession` | `toSession` | Optional | API FUNCTION EXISTS BUT UI MISSING |
| `POST /time/od` | `note` | None (No UI Form) | `note` | `note` | `note` | Optional | API FUNCTION EXISTS BUT UI MISSING |
