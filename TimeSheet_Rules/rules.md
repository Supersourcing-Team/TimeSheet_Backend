# Timesheet Management System - Backend AI Context & Rules

> This file defines the permanent development context and coding rules for every AI coding session and developer working on the Timesheet Management System.
> Always follow these instructions to maintain consistency across the codebase.

---

# Project Overview

- **Project Name:** Timesheet Management System
- **Backend Framework:** FastAPI (Python 3.13+)
- **Architecture Pattern:** Modular Monolith
- **Current Stage:** MVP / Production Active

---

# Tech Stack

### Backend Infrastructure
- **Framework:** FastAPI
- **Language:** Python 3.13+
- **ORM:** SQLAlchemy 2.x (Async)
- **Database Driver:** AsyncPG
- **Database Engine:** PostgreSQL (Neon Cloud / Local PostgreSQL)
- **Schema Migrations:** Alembic
- **Validation & Serialization:** Pydantic v2 & `pydantic-settings`

### Authentication & Security
- **Identity Provider:** Google OAuth SSO (ID Token Verification)
- **Session Strategy:** Stateless JWT Tokens
  - **Access Token Expiry:** 30 Minutes
  - **Refresh Token Expiry:** 7 Days

### Background Tasks & Services
- **Job Scheduler:** APScheduler (Weekly locks & reminder tasks in `app/scheduler/`)
- **Email Dispatch:** SMTP Service (`app/services/email_service.py`)
- **Reporting & Documents:** Excel Generation (`excel_service.py`), PDF Generation (`pdf_service.py`)

### Frontend Reference Stack
- **Framework:** React 18 + Vite + TypeScript
- **Styling:** Tailwind CSS + Lucide React Icons
- **API Base Route:** `/api/v1`

---

# Repository Directory & Folder Structure

The project follows a structured **Modular Monolith** architecture where domain entities have centralized models in `app/models/` and feature logic inside `app/modules/`.

```
timesheet-management-Backend/
├── alembic/                      # Database migrations & revision scripts
├── app/
│   ├── api/                      # Main API Routing layer
│   │   └── router.py             # Aggregates module routers under `/api/v1` & `/health`
│   ├── common/                   # Global helpers, response wrappers, file processing
│   │   ├── file_handler.py       # File upload & storage handlers
│   │   ├── helpers.py            # Utility helper methods
│   │   ├── pagination.py         # Reusable pagination calculation utilities
│   │   ├── responses.py          # Standardized API response formatters (`success_response`, `error_response`)
│   │   └── utils.py              # Miscellaneous shared utilities
│   ├── core/                     # System configuration & core singletons
│   │   ├── config.py             # Environment configuration (`Settings` class)
│   │   ├── constants.py          # App constants & defaults
│   │   ├── database.py           # Async SQLAlchemy engine & AsyncSession provider
│   │   ├── exceptions.py         # Custom application exceptions
│   │   ├── logger.py             # Centralized logging setup
│   │   ├── permissions.py        # Permission definitions
│   │   └── security.py           # Encryption, hashing, token generation
│   ├── dependencies/             # FastAPI request-scoped dependency providers
│   │   ├── auth.py               # Token verification (`get_current_user`, `get_current_active_user`)
│   │   ├── database.py           # Database session dependency (`get_db`)
│   │   ├── pagination.py         # Page/limit query parameters parser
│   │   └── permissions.py        # Role guards (`require_roles`, `require_admin`, `require_project_manager`, `require_account_manager`)
│   ├── models/                   # Centralized SQLAlchemy ORM Models
│   │   ├── client.py             # Client entity model
│   │   ├── holiday.py            # Company holiday model
│   │   ├── leave_balance.py      # User leave quota balance model
│   │   ├── leave_request.py      # Employee leave application model
│   │   ├── leave_type.py         # Leave categorization model
│   │   ├── project.py            # Project entity model
│   │   ├── project_assignment.py # User-to-Project allocation model
│   │   ├── role.py               # User role definitions model
│   │   ├── timesheet.py          # Work hours log entry model
│   │   ├── tool.py               # Hardware/Software tool asset model
│   │   ├── tool_allocation.py    # User tool assignment model
│   │   ├── user.py               # User profile & auth account model
│   │   └── weekend_work.py       # Overtime weekend work request model
│   ├── modules/                  # Modular Monolith Domain Feature Modules
│   │   ├── auth/                 # Google SSO, JWT refresh, logout, profile (`/me`)
│   │   ├── clients/              # Client catalog management
│   │   ├── dashboard/            # Executive & manager metrics summaries
│   │   ├── holidays/             # Calendar holidays management
│   │   ├── leave_balances/       # Employee leave balance tracking
│   │   ├── leave_requests/       # Leave application submit & approval workflows
│   │   ├── leave_types/          # Admin leave types definition
│   │   ├── project_assignments/  # Project user allocation management
│   │   ├── projects/             # Project creation, billing, rates
│   │   ├── reports/              # Analytics aggregation & file exports
│   │   ├── roles/                # System role management
│   │   ├── timesheets/           # Timesheet logging, weekly locks & calculations
│   │   ├── tool_allocations/     # Asset tool allocation tracking
│   │   ├── tools/                # Company tool inventory catalog
│   │   ├── users/                # User accounts & employee profiles
│   │   └── weekend_work/         # Overtime weekend work request workflows
│   ├── scheduler/                # APScheduler Background Job Services
│   │   ├── scheduler.py          # Scheduler initialization and startup lifecycle
│   │   ├── weekly_timesheet_lock.py  # Automated weekly timesheet locking task
│   │   └── weekly_timesheet_reminder.py # Email notification task for timesheet submission
│   ├── services/                 # Shared Business Utility Services
│   │   ├── email_service.py      # SMTP Email sender
│   │   ├── excel_service.py      # OpenPyXL report generator
│   │   ├── notification_service.py # In-app notification dispatcher
│   │   └── pdf_service.py        # PDF document renderer
│   ├── templates/                # HTML/Text templates for emails and reports
│   └── main.py                   # FastAPI Application Entry Point (Middlewares, Router, Exception Handlers)
├── tests/                        # Automated Pytest suite
├── seed_users.py                 # Initial database seeding script
├── alembic.ini                   # Alembic configuration
└── TimeSheet_Rules/
    └── rules.md                  # Development context & AI guidelines (this file)
```

---

# Modular Architecture & Responsibilities

Every domain module in `app/modules/<module_name>/` follows strict layer isolation:

```
FastAPI Router (app/modules/*/router.py)
       │
       ▼
Service Layer (app/modules/*/service.py)
       │
       ▼
Repository Layer (app/modules/*/repository.py)
       │
       ▼
SQLAlchemy Async ORM (app/models/*.py)
```

### Component Responsibilities

1. **Router (`router.py`)**
   - Pure HTTP endpoints (`APIRouter`).
   - Request parameter parsing & Pydantic schema validation.
   - Dependency Injection (`get_db`, `get_current_active_user`, `require_roles`).
   - Delegates business execution to the Service Layer.
   - Returns responses using standardized response helpers from `app.common.responses`.
   - **NEVER** write database queries or business logic in routers.

2. **Service (`service.py`)**
   - Implements core business logic, policies, and domain calculations.
   - Handles transactions and multi-step workflows.
   - Validates business rules (e.g. leave balances, max daily hours, project assignment checks).
   - Invokes Repositories for DB persistence.
   - Triggers secondary services (`email_service`, `notification_service`).

3. **Repository (`repository.py`)**
   - Performs SQLAlchemy Async queries (`AsyncSession`).
   - Provides CRUD, search filters, pagination, and lookup operations.
   - Performs **NO** business logic, validation, or cross-repository calls.

4. **Schema (`schema.py`)**
   - Defines request payload models and response models using Pydantic v2.

5. **Centralized Models (`app/models/`)**
   - Single source of truth for database table definitions and SQLAlchemy relationships.
   - Keeps models centralized to avoid circular imports across feature modules.

6. **Validator (`validator.py` - Optional)**
   - Complex data structure or business logic validation routines.

---

# Architecture Rules

- **Strict Downward Flow:** `Router` -> `Service` -> `Repository` -> `Database`.
- **Forbidden Patterns:**
  - ❌ `Router` executing raw SQLAlchemy queries or importing DB models directly for queries.
  - ❌ `Repository` executing business validation logic or invoking another `Repository`.
  - ❌ `Service` returning raw SQLAlchemy ORM entities directly to the client without Pydantic serialization.
  - ❌ Bypassing role-based access dependencies on protected routes.

---

# Authentication & Frontend Integration

### Auth Architecture Flow
1. **Frontend Google Login:** Client signs in with Google Identity and obtains a Google Credential ID Token.
2. **Backend Auth Verification (`POST /api/v1/auth/google/login`):**
   - Validates Google ID token via `GOOGLE_CLIENT_ID`.
   - Checks if user email exists in database (User must be pre-created by Admin).
   - Generates JWT Access Token (30 min) and Refresh Token (7 days).
3. **Session Maintenance:**
   - Client sends token in header: `Authorization: Bearer <access_token>`.
   - Endpoint `GET /api/v1/auth/me` retrieves active user profile.
   - Endpoint `POST /api/v1/auth/refresh` refreshes access tokens using refresh tokens.

### Role Mapping Strategy
Backend system roles map cleanly to frontend user interfaces:
- `Admin` ➔ Admin Dashboard (User creation, system roles, leave approvals, holidays, settings)
- `Project_Manager` ➔ PM View (Client management, project creation, weekend work approvals, team allocation)
- `Account_Manager` ➔ Account Manager View (Financial analytics, billing, project report exports)
- `Employee` ➔ Employee View (Timesheet logging, leave requests, weekend work requests)

---

# Core Business Rules

1. **Daily Hours Limit:** Maximum 8 standard hours per day per employee.
2. **Weekly Target:** Standard full-time target is 40 hours per week.
3. **No Self-Registration:** Users cannot register accounts publicly. Accounts must be created by an Admin.
4. **Account Soft Deletion:** Users and key entities are soft-deleted (`is_active = False` or `deleted_at`) rather than hard deleted from the database.
5. **Approval Matrix:**
   - **Leave Requests:** Approved exclusively by `Admin` role.
   - **Weekend Work Overtime:** Approved by `Project_Manager` assigned to the project.
6. **Automated Weekly Lock:** Timesheets are automatically locked after the submission deadline via APScheduler background tasks (`weekly_timesheet_lock.py`).
7. **Timesheet Entry Requirements:** Each log entry must link to a valid Project, include specified hours, indicate billable status, and provide a clear work summary.

---

# Standard API Contract & Format

- **Base URL:** `/api/v1`
- **URL Naming Convention:** `kebab-case` (e.g. `/leave-requests`, `/weekend-work`, `/tool-allocations`)
- **Field Naming Convention:** `snake_case` (e.g. `user_id`, `project_manager_id`, `leave_type_id`)

### Standard Success Response Wrapper
```json
{
  "success": true,
  "message": "Resource fetched successfully",
  "data": {},
  "errors": null
}
```

### Standard Error Response Wrapper
```json
{
  "success": false,
  "message": "Validation failed",
  "data": null,
  "errors": [
    {
      "field": "hours",
      "message": "Daily total hours cannot exceed 8"
    }
  ]
}
```

### Standard Status Codes
- `200 OK`: Successful fetch/update.
- `201 Created`: Successful creation.
- `400 Bad Request`: Invalid request input / business rule violation.
- `401 Unauthorized`: Missing or invalid authentication token.
- `403 Forbidden`: Insufficient role permissions.
- `404 Not Found`: Requested resource does not exist.
- `422 Unprocessable Entity`: Schema validation error.
- `500 Internal Server Error`: Unhandled server error.

---

# Branching Strategy & Workflow (2 Developers)

Given the team size (2 developers) and multiple deployment environments (`dev`, `staging`, `uat`, `main`), we follow a **Lightweight Environment-Branching Model (Modified GitHub Flow)**. 

### Core Branches
- `main` (Production): Stable code deployed to production. Should only accept merges from `staging`/`uat`.
- `staging` / `uat` (Pre-production): Used for final QA or client demo before production. Accepts merges from `dev`.
- `dev` (Integration): The default branch where developers merge all new features and fixes. 

### Workflow Steps
1. **Create a Feature Branch:** Always branch off `dev`.
   - Naming convention: `feature/<short-desc>` (e.g. `feature/user-role`, `feature/leave-approval`)
   - Bugfix convention: `bugfix/<short-desc>` (e.g. `bugfix/auth-token-refresh`)
2. **Commit Often:** Write clear, descriptive commit messages. Avoid stashing dirty working states and pushing them to remote branches.
3. **Pull Request (PR) to `dev`:** 
   - Before opening a PR, always rebase or merge `origin/dev` into your feature branch to resolve conflicts locally.
   - The other developer **must** review and approve the PR before it gets merged.
4. **Deploy to Dev/Staging:** Once merged into `dev`, code is tested in the dev environment. When a release is ready, a PR is opened from `dev` to `staging`/`uat`, and eventually to `main`.

### Rules for Commits
- ❌ **NO direct commits to `main`, `staging`, or `dev`.** All changes must go through a feature/bugfix branch and a PR.
- ❌ **Avoid pushing WIP Stashes:** E.g., avoid creating stash commits on remote branches. Use standard commits and squash them later if needed.
- ✅ **Keep branches short-lived:** Merge your features back to `dev` within a few days to avoid massive merge conflicts.

---

# AI Development Workflow & Step Checklist

When creating or extending any feature module:

1. **Review Business Rules:** Confirm permissions, role capabilities, and validation parameters.
2. **Define/Update Model:** Add or verify SQLAlchemy model in `app/models/`.
3. **Create Migration:** Generate and apply Alembic migration (`alembic revision --autogenerate -m "..."`).
4. **Create Schemas:** Define Pydantic request & response schemas in `app/modules/<module>/schema.py`.
5. **Implement Repository:** Build query methods in `app/modules/<module>/repository.py`.
6. **Implement Service:** Build business logic & rule validation in `app/modules/<module>/service.py`.
7. **Implement Router:** Add HTTP endpoints in `app/modules/<module>/router.py` using `app.common.responses`.
8. **Register Router:** Include module router in `app/api/router.py`.
9. **Test & Verify:** Run manual or automated tests to confirm end-to-end functionality.