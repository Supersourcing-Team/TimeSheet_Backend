# Timesheet Management System - Backend

Backend service for the **Timesheet Management System**, built using **FastAPI** with an asynchronous, modular architecture. The system manages employees, projects, timesheets, leave requests, holidays, tool allocations, and reporting.

---

## Tech Stack

* **Framework:** FastAPI
* **Language:** Python 3.14+
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy 2.0 (Async + `asyncpg`)
* **Migrations:** Alembic
* **Authentication:** Google OAuth2 + JWT
* **Scheduler:** APScheduler
* **Email:** SMTP + Jinja2 Templates

---

## Prerequisites

* **Python:** 3.14+
* **Database:** PostgreSQL 14+
* **Tools:** Git, `pip`

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd timesheet-management-Backend
```

### 2. Create a virtual environment

**Windows**

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

The **only value you must change** before seeding is `ADMIN_EMAIL`:

```env
# Set this to YOUR work email — this becomes the first Admin account
ADMIN_EMAIL=you@yourcompany.com

# Update DATABASE_URL if your Postgres credentials differ from the default
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/timesheet_db

# Obtain from Google Cloud Console → Credentials
GOOGLE_CLIENT_ID=your_google_client_id
```

### 5. Run database migrations & seed

This single command applies all schema migrations **and** seeds the four
system roles plus your default Admin account (using `ADMIN_EMAIL` from `.env`):

```bash
alembic upgrade head
```

> **That's it.** After this, the Admin can log in via Google OAuth to begin
> onboarding the rest of the team.

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

- **Application API:** `http://localhost:8000`
- **Swagger Interactive Docs:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`
- **Health Check Endpoint:** `http://localhost:8000/api/v1/health`

---

## Project Structure

```text
timesheet-management-Backend/
│
├── app/
│   ├── api/                  # Main API router and endpoints
│   ├── common/               # Common utilities and helpers
│   ├── core/                 # App configs, database session, and central models registry
│   ├── dependencies/         # FastAPI dependency injection
│   ├── modules/              # Modular domain-driven feature components
│   │   ├── auth/             # Authentication & OAuth
│   │   ├── clients/          # Client management (includes model.py, router, service, etc.)
│   │   ├── dashboard/        # Dashboard analytics
│   │   ├── holidays/         # Company holidays
│   │   ├── leave_balances/   # Annual leave tracking
│   │   ├── leave_requests/   # Leave applications & approvals
│   │   ├── leave_types/      # Types of leave
│   │   ├── milestones/       # Project milestones
│   │   ├── project_assignments/ # User-project assignments
│   │   ├── projects/         # Project management
│   │   ├── reports/          # Timesheet & leave reports
│   │   ├── roles/            # Role-based permissions
│   │   ├── settings/         # System settings
│   │   ├── timesheets/       # Daily timesheets & entries
│   │   ├── tool_allocations/ # Software license allocation
│   │   ├── tools/            # Software tools inventory
│   │   ├── users/            # Employee / User management
│   │   ├── weekend_work/     # Weekend & holiday work requests
│   │   └── working_calendar/ # Working calendar definitions
│   ├── scheduler/            # APScheduler background tasks
│   ├── services/             # External/Shared services (Email, PDF, etc.)
│   ├── templates/            # Email templates (Jinja2)
│   └── main.py               # FastAPI app initialization
│
├── alembic/                  # Database migration scripts (consolidated into a single version)
│   └── versions/             # Migration version histories
├── tests/                    # Unit and integration tests
├── .env                      # Environment variables (git-ignored)
├── .gitignore                # Git ignore configuration
├── alembic.ini               # Alembic configuration
├── pyproject.toml            # Project configuration
├── requirements.txt          # Python package dependencies
└── README.md                 # Project documentation
```

---

## Modules

* **Authentication:** Google OAuth2, JWT generation, and token validation.
* **Users & Roles:** User management with Role-Based Access Control (RBAC).
* **Clients & Projects:** Manage client information, project allocations, and resource assignments.
* **Timesheets:** Daily logging of work hours, project tasks, and manager approval workflows.
* **Weekend & Holiday Work:** Request and approval process for weekend working hours.
* **Leave Management:** Custom leave types, automatic balance tracking, and approval flows.
* **Holidays:** Organization holiday calendar management.
* **Tools & Allocations:** Track software licenses and tool assignments per developer/team.
* **Dashboard & Reports:** Summary metrics, timesheet exports, and utilization reports.

---

## Database Schema

The database consists of **17 core tables**:

1. **`roles`**: Defines user authority levels (Admin, Manager, Employee).
2. **`users`**: Employee accounts, auth metadata, and manager reporting structure.
3. **`clients`**: Client profiles and contacts.
4. **`projects`**: Projects linked to clients.
5. **`project_assignments`**: Assigns employees to active projects.
6. **`milestones`**: Project milestones and deliverables tracking.
7. **`milestone_assignments`**: Assigns users and budgets to specific milestones.
8. **`timesheets`**: Logged daily working hours and activity descriptions.
9. **`weekend_work_requests`**: Approval workflow for extra weekend hours.
10. **`leave_types`**: Configurable leave policies (Casual, Sick, Earned, etc.).
11. **`leave_balances`**: Track remaining leave quotas per employee per year.
12. **`leave_requests`**: Employee leave applications with status tracking.
13. **`holidays`**: Public and company holiday records.
14. **`working_calendar`**: Organization's standard working days and hours.
15. **`tools`**: Inventory of software/hardware tools.
16. **`tool_allocations`**: Track active tool assignments per user.
17. **`system_settings`**: Configurable platform-wide global settings.

---

## Authentication Flow

* **Google OAuth2 Login** for seamless enterprise authentication.
* **JWT (JSON Web Tokens)** for stateless session management.
* **Role-Based Authorization (RBAC)** ensuring restricted endpoint access.
* **Admin-Managed Onboarding**: Accounts created by Admins (no public self-registration).

---

## Development Status

| Module / Component | Status | Description |
| :--- | :---: | :--- |
| **Project Architecture** | ✅ Completed | Modular directory structure & FastAPI setup |
| **Database Connection** | ✅ Completed | Async Engine (`sqlalchemy.ext.asyncio` + `asyncpg`) |
| **ORM Models** | ✅ Completed | 17 core models defined and modularized |
| **Alembic Migrations** | ✅ Completed | Single consolidated initial migration executed against PostgreSQL |
| **Health API** | ✅ Completed | `/api/v1/health` verifying live DB connection |
| **Authentication Module** | ✅ Completed | OAuth + JWT login implementation |
| **Feature APIs** | ✅ Completed | CRUD routers & services for Timesheets, Leaves, etc. |

---

## Git Workflow

Features are developed in separate feature branches branched off `dev`.

```text
main
 └── dev
      ├── feature/authentication
      ├── feature/timesheets
      └── bugfix/fix-migration
```

### Commit Convention

```text
feat: add user management endpoints
fix: resolve database connection pooling timeout
refactor: streamline async session dependency
docs: update README with setup instructions
```

---

## Developers

* **Govinda** — Developer
* **Balram** — Developer

---

Happy Coding! 🚀
