# Keka Integration Architecture

## 1. Architectural Overview

The integration between **Keka HRMS** and the internal **Employee Timesheet & HR Management System** connects external HR master records with internal timesheet logging, approval workflows, working calendars, and leave tracking.

```
      +-------------------------------------------------------------+
      |                       Keka HR API v1                        |
      +-------------------------------------------------------------+
                                  ▲       │
             Local -> Keka Pushes │       │ Keka -> Local Pulls
                                  │       ▼
      +-------------------------------------------------------------+
      |                   KekaClient (HTTP / OAuth2)                |
      +-------------------------------------------------------------+
                                  ▲       │
                                  │       ▼
      +-------------------------------------------------------------+
      |       Keka Integration Services & Background Sync Jobs      |
      |   (KekaService, KekaLeaveService, KekaAttendanceService)    |
      +-------------------------------------------------------------+
                                  ▲       │
                                  │       ▼
      +-------------------------------------------------------------+
      |        Existing Project Business Logic & Repositories       |
      |   (Users, Departments, Leave Requests, Working Calendar)   |
      +-------------------------------------------------------------+
                                  ▲       │
                                  │       ▼
      +-------------------------------------------------------------+
      |                 Existing PostgreSQL Database                |
      |   (users, departments, leave_requests, holidays, mappings)  |
      +-------------------------------------------------------------+
```

---

## 2. Feature Architecture Matrix

| Feature | Source of Truth | Direction | Strategy | Local Storage | Trigger |
|---|---|---|---|---|---|
| **Employee Master Data** | Keka HR | Keka → Local | Scheduled / On-Demand Sync | `users`, `keka_employee_mappings` | Admin manual sync or scheduled background job |
| **Department Master** | Keka HR | Keka → Local | Scheduled / On-Demand Sync | `departments` | Admin sync / Employee sync trigger |
| **Leave Types & Policies** | Keka HR | Keka → Local | On-Demand Sync | `leave_types.keka_leave_type_id` | Configuration setup / Admin sync |
| **Leave Requests (Submission)** | Internal Portal | Local → Keka | Real-time on Approval + Retry | `leave_requests` (`synced_to_keka`, `keka_leave_request_id`) | Manager approves leave locally |
| **Leave Statuses (External)** | Keka HR | Keka → Local | Scheduled / On-Demand Pull | `leave_requests.status` | Scheduled sync / Admin poll |
| **Leave Balances** | Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | Employee opens leave application modal |
| **Attendance Clocks** | Internal Portal / Keka | Local → Keka | Real-time Punch Push | `keka_employee_mappings` (audit logs) | Employee logs punch-in/out in portal |
| **Attendance Ingestion & Audit** | Keka HR | Keka → Local | On-Demand Pull & Cross-Audit | Memory cross-audit with `leave_requests` | Timesheet review / Attendance Exceptions dashboard |
| **Attendance Exceptions Signal** | Composite (Keka + Local) | Bidirectional Audit | On-Demand Evaluation | Evaluated dynamically | Manager/Admin opens Attendance Exceptions |
| **Holiday Calendar** | Keka HR | Keka → Local | Scheduled / On-Demand Sync | `holidays` table | Admin holiday sync / Yearly rollover |
| **Weekly-Off Policy** | Keka HR | Keka → Local | On-Demand Sync | `working_calendar.working_days` (JSON) | Admin sync / Policy change |
| **Weekend Work Overtime** | Internal Portal | Local (Internal) | Internal Business Logic (influenced by `working_calendar`) | `weekend_work_requests` | Employee applies for weekend overtime |
| **Work From Home (WFH)** | Keka HR / Portal | Bidirectional | On-Demand Submission & Query | API query / Mapping | Admin or User submits WFH request |
| **On Duty (OD)** | Keka HR / Portal | Bidirectional | On-Demand Submission & Query | API query / Mapping | Admin or User submits OD request |
| **Shift Policies** | Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | Shift policy inspection |
| **Attendance Capture Scheme**| Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | Attendance settings inspection |
| **Penalisation Policies** | Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | Attendance settings inspection |
| **Regularisation Requests**| Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | HR audit inspection |
| **Employee Documents** | Keka HR | Read-only Keka | On-Demand Live Read | Ephemeral API response | HR file review |

---

## 3. Detailed Data Flows

### 3.1 Employee Synchronization (Keka → Local)
1. Keka API returns active, notice-period, and relieved employees via `GET /hris/employees`.
2. Existing local employees are identified by:
   - Primary: Matching `keka_employee_mappings.keka_employee_id`.
   - Secondary: Matching `users.email` (case-insensitive).
   - Tertiary: Matching `users.employee_id` with Keka `employeeNumber`.
3. If matched:
   - Names, joining date, and status are updated (`Relieved`/`Exited` in Keka updates local status to `Inactive`).
   - Department is resolved against local `departments` table (or provisioned if missing).
   - `keka_employee_mappings` record is linked and updated with `last_synced_at`.
4. If missing and `create_missing=True`:
   - New `User` is provisioned with default `Employee` role.
   - 1:1 mapping entry is written.

### 3.2 Leave Submission Flow (Local → Keka)
1. Employee applies for leave through the local portal (`POST /api/v1/leave-requests`).
2. Leave request is created locally in `Pending` status.
3. Manager approves leave locally (`POST /api/v1/leave-requests/{id}/approve`).
4. Approval triggers synchronous background sync via `KekaLeaveService.sync_leave_to_keka`:
   - Resolves local `user_id` to Keka UUID using `keka_employee_mappings`.
   - Resolves `leave_type_id` to `keka_leave_type_id`.
   - Submits `POST /time/leaverequests` to Keka API.
   - On success: updates `synced_to_keka = True`, stores `keka_leave_request_id = response.data`, sets `last_synced_at`.
   - On failure: marks `synced_to_keka = False`, records `last_sync_error`.
5. Background retry worker or `POST /api/v1/keka/sync/leaves/pending` recovers any un-synced requests.

### 3.3 Attendance & Exception Signal Flow
1. Keka logs raw biometric or web punches.
2. When HR/Manager requests attendance data (`GET /api/v1/keka/attendance`):
   - Normalizes Keka records (`Present`, `Half Day`, `Absent`, `Weekly Off`, `Holiday`).
   - Maps each entry to local `User` via `keka_employee_mappings`.
3. When inspecting exceptions (`GET /api/v1/keka/attendance/exceptions`):
   - Cross-references Keka `Absent` status with local `leave_requests` (approved or pending).
   - Flags employees marked `Absent` without leave as `absent_without_leave`.
   - Flags entries with clock-in but no clock-out as `missing_punch`.

### 3.4 Working Calendar & Weekly Off Alignment
1. Keka weekly off rules are pulled via `GET /time/weeklyoffpolicies`.
2. `KekaAttendanceService.sync_weekly_off_policy_to_calendar` evaluates non-working days.
3. Updates `working_calendar.working_days` JSON (`monday: True, ..., saturday: False, sunday: False`).
4. Existing `working_days_calculator.py` and `weekend_work` overtime validators immediately inherit these rules for timesheet and overtime calculations.

---

## 4. Failure, Retry & Idempotency Guarantees
- **Local DB Succeeded, Keka Failed**: Record retains `synced_to_keka = False` and `last_sync_error`. Can be retried cleanly at any time without duplicating local records.
- **Keka Succeeded, Local DB Update Failed**: `keka_leave_request_id` lookup via `LeaveRequestRepository.get_by_keka_id` allows reconciliation without re-submitting to Keka.
- **Duplicate Prevention**:
  - Employee mappings enforce unique constraints on `keka_employee_id` and `local_user_id`.
  - Holiday sync matches by `date`.
  - Department sync matches by case-insensitive `name`.
  - Leave submissions include `note="Local Leave ID: {id}"` for audit deduplication.
