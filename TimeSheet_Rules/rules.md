# Timesheet Management System - Backend Context

## What We're Building
FastAPI backend for employee timesheet tracking with PostgreSQL (Neon DB). Employees log daily hours (max 8/day, 40/week) across multiple projects with billable/non-billable flags. Google SSO only authentication. Admin onboards users, no self-registration.

## Tech Stack
FastAPI | PostgreSQL | SQLAlchemy 2.0 (async) | asyncpg | Alembic | Google SSO + JWT | APScheduler | SMTP Email

## User Roles
- **Admin:** Full system access, user onboarding, role assignment
- **Project Manager:** Create projects, assign employees, review team timesheets, approve leaves
- **Account Manager:** View project financials (cost, revenue, profit)
- **Employee:** Submit daily timesheets, apply leaves, view own data

## Critical Business Rules (NEVER BREAK)
1. Daily timesheet hours ≤ 8 across all projects
2. Weekly target = 40 hours
3. Every entry needs: project, hours, billable flag, work summary
4. Only Google SSO login (users created by admin first)
5. Profit = Revenue - (Tools Cost + Billable Hours Cost)
6. Soft delete only (status field), never hard delete users
7. Server-side validation on every endpoint

## Folder Structure (Don't Modify Without Discussion)

The project structure is finalized for the current phase and will be updated as required during the development lifecycle.
│
├──Timesheet_backend/
│   │
│   ├── app/
│   │   │
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── permissions.py
│   │   │   ├── constants.py
│   │   │   ├── exceptions.py
│   │   │   ├── logger.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── common/
│   │   │   ├── responses.py
│   │   │   ├── pagination.py
│   │   │   ├── helpers.py
│   │   │   ├── utils.py
│   │   │   ├── file_handler.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── dependencies/
│   │   │   ├── auth.py
│   │   │   ├── permissions.py
│   │   │   ├── pagination.py
│   │   │   ├── database.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── services/
│   │   │   ├── email_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── excel_service.py
│   │   │   ├── pdf_service.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── models/
│   │   │   ├── role.py
│   │   │   ├── user.py
│   │   │   ├── holiday.py
│   │   │   ├── leave_type.py
│   │   │   ├── leave_balance.py
│   │   │   ├── leave_request.py
│   │   │   ├── client.py
│   │   │   ├── project.py
│   │   │   ├── project_assignment.py
│   │   │   ├── tool.py
│   │   │   ├── tool_allocation.py
│   │   │   ├── timesheet.py
│   │   │   ├── weekend_work.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── modules/
│   │   │
│   │   │   ├── auth/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── jwt.py
│   │   │   │   ├── oauth.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── users/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── validator.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── roles/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── clients/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── projects/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── validator.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── project_assignments/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── tools/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── tool_allocations/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── holidays/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── leave_types/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── leave_balances/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── leave_requests/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── validator.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── timesheets/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── validator.py
│   │   │   │   ├── helper.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── weekend_work/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   ├── dashboard/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schema.py
│   │   │   │   └── __init__.py
│   │   │   │
│   │   │   └── reports/
│   │   │       ├── router.py
│   │   │       ├── service.py
│   │   │       ├── repository.py
│   │   │       ├── schema.py
│   │   │       ├── exporter.py
│   │   │       └── __init__.py
│   │   │
│   │   ├── scheduler/
│   │   │   ├── scheduler.py
│   │   │   ├── weekly_timesheet_reminder.py
│   │   │   ├── weekly_timesheet_lock.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── templates/
│   │   │   └── emails/
│   │   │       ├── welcome.html
│   │   │       ├── leave_approved.html
│   │   │       ├── leave_rejected.html
│   │   │       └── weekly_timesheet_reminder.html
│   │   │
│   │   ├── main.py
│   │   └── __init__.py
│   │
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── tests/
│   │
│   ├── requirements.txt
│   ├── .env
│   ├── .gitignore
│   ├── alembic.ini
      └── README.md

      
## Module Pattern (Every Feature Module Must Follow)
modules/{feature_name}/
├── init.py
├── router.py # FastAPI APIRouter with endpoint definitions
├── service.py # Business logic, validation orchestration, transaction management
├── repository.py # Async SQLAlchemy database queries (CRUD operations)
├── schema.py # Pydantic v2 request/response models
└── validator.py # Custom validation functions (optional, if complex logic needed)


## Database Schema (14 Tables)

### Core Tables
- **roles:** id, name(unique: Admin/Project_Manager/Account_Manager/Employee), description, created_at
- **users:** id, role_id(FK→roles), employee_id(unique), first_name, last_name, email(unique), joining_date, status(default:Active), created_at, updated_at

### HR Tables
- **holidays:** id, date, name, created_at
- **leave_types:** id, name(unique), description, is_active(default:true), created_at, updated_at
- **leave_balances:** id, user_id(FK), leave_type_id(FK), year, allocated_days(default:0), used_days(default:0), updated_at | UNIQUE(user_id, leave_type_id, year)
- **leave_requests:** id, user_id(FK), leave_type_id(FK), start_date, end_date, reason, status(default:Pending), managers_user_id(FK→users), rejection_reason, created_at, updated_at

### Project Tables
- **clients:** id, name, email, phone, created_at
- **projects:** id, client_id(FK), project_manager_id(FK→users), project_name(unique), description, budget, start_date, end_date, status(default:Planning), created_at, updated_at
- **project_assignments:** id, project_id(FK), user_id(FK), created_at | UNIQUE(project_id, user_id)

### Tools Tables
- **tools:** id, name, category(AI/API/Testing/Cloud), cost_per_month, status(default:Active), created_at
- **tool_allocations:** id, project_id(FK), tool_id(FK), allocation_date, deallocation_date(nullable), status(default:Active), created_at

### Timesheet Tables
- **timesheets:** id, user_id(FK), project_assignment_id(FK), timesheet_date, hours(decimal), is_billable(boolean), task_description, work_summary, created_at, updated_at
- **weekend_work_requests:** id, project_assignment_id(FK), work_date, reason, status(default:Pending), approved_by(FK→users), approved_at, created_at

## API Endpoints Quick Reference

### Auth (Public)
- POST `/api/v1/auth/google/login` - Google ID token → JWT pair
- POST `/api/v1/auth/refresh` - Refresh expired token
- POST `/api/v1/auth/logout` - Invalidate token

### Users (Admin mostly)
- GET/POST `/api/v1/users/` - List/Create users
- GET/PATCH `/api/v1/users/me/` - Own profile
- GET/PATCH/DELETE `/api/v1/users/{id}` - User operations
- GET `/api/v1/roles/` - List roles

### Clients
- GET/POST `/api/v1/clients/`
- GET/PATCH `/api/v1/clients/{id}`
- GET `/api/v1/clients/{id}/projects`

### Projects
- GET/POST `/api/v1/projects/`
- GET/PATCH `/api/v1/projects/{id}`
- GET `/api/v1/projects/{id}/assignments`
- POST `/api/v1/projects/{id}/assign` - Assign employees
- DELETE `/api/v1/projects/{id}/assign/{user_id}`

### Timesheets (Core)
- POST `/api/v1/timesheets/` - Submit daily entries (validates ≤8hrs)
- GET `/api/v1/timesheets/` - List with filters
- GET/PATCH `/api/v1/timesheets/{id}`
- GET `/api/v1/timesheets/weekly-summary` - Hours breakdown
- GET `/api/v1/timesheets/daily/{user_id}/{date}`
- GET `/api/v1/my-timesheets/`

### Leaves
- GET `/api/v1/leave-types/`
- GET `/api/v1/leave-balances` - Own balance
- POST `/api/v1/leave-requests/` - Apply
- GET `/api/v1/leave-requests/`
- PATCH `/api/v1/leave-requests/{id}/approve|reject`

### Others
- GET/POST `/api/v1/holidays/`
- GET/POST/PATCH `/api/v1/tools/`
- POST `/api/v1/tools/allocate` | PATCH `/api/v1/tools/deallocate/{id}`
- POST `/api/v1/weekend-work/` | GET `/api/v1/weekend-work/`
- PATCH `/api/v1/weekend-work/{id}/approve|reject`

### Dashboard (Account Manager)
- GET `/api/v1/dashboard/overview`
- GET `/api/v1/dashboard/project/{id}/financials`
- GET `/api/v1/dashboard/project/{id}/hours`

## API Conventions
- **Response wrapper:** `{success: bool, message: str, data: {}, errors: null}`
- **Pagination:** `?page=1&limit=20` returns `{total, page, limit, total_pages, items: []}`
- **Auth header:** `Authorization: Bearer <access_token>`
- **URLs:** kebab-case (`/leave-requests`, `/weekend-work`)
- **Fields:** snake_case (`project_manager_id`, `leave_type_id`)
- **Error codes:** 400 (validation), 401 (auth), 403 (forbidden), 404, 422, 500

## Authentication Flow
1. Admin creates user via `POST /users/` with company email
2. User visits frontend, clicks "Login with Google"
3. Frontend gets Google ID token via Google Identity Services
4. Sends to `POST /auth/google/login` with `{credential: "google_id_token"}`
5. Backend verifies token with Google APIs
6. Checks user exists in DB with status=Active
7. Returns JWT access_token (30min) + refresh_token (7days)
8. JWT payload: `{sub: user_id, email, role, employee_id, exp, iat}`

## Permission Dependencies (FastAPI)
```python
get_current_user           # Extract JWT, return user from DB
get_current_active_user    # Above + check status==Active
require_admin              # Role==Admin
require_project_manager    # Role==Project_Manager
require_account_manager    # Role==Account_Manager
require_roles([...])       # Check if role in list