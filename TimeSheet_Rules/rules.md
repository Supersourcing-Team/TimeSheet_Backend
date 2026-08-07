# Timesheet Management System Backend AI Context

> This file defines the permanent development context for every AI coding session.
> Always follow these instructions unless explicitly overridden.

---

# Project

Timesheet Management System

Backend Framework:
FastAPI

Architecture:
Modular Monolith

Current Stage:
MVP

---

# Tech Stack

Backend
- FastAPI
- Python 3.13+
- SQLAlchemy 2.x (Async)
- AsyncPG
- PostgreSQL (Neon)

Authentication
- Google OAuth
- JWT Access Token
- JWT Refresh Token

Migration
- Alembic

Background Jobs
- APScheduler

Email
- SMTP

Validation
- Pydantic v2

---

# Folder Structure

Every feature follows exactly this structure.

modules/

feature/

router.py
service.py
repository.py
schema.py
validator.py (optional)

Responsibilities

Router

- HTTP endpoints only
- Validation
- Dependency Injection
- Calls service

Service

- Business Logic
- Transactions
- Rules
- Calls repositories

Repository

- SQLAlchemy Queries only
- CRUD
- Never business logic

Schema

- Request Models
- Response Models

Validator

- Complex validation

Never mix responsibilities.

---

# Architecture Rules

Always keep

API

↓

Service

↓

Repository

↓

Database

Never

Router → Database

Never

Router → SQLAlchemy

Never

Repository → Business Logic

Never

Repository calling another Repository

Keep repositories independent.

---

# Authentication

Only Google Login.

No email/password.

Flow

Frontend

↓

Google Identity

↓

ID Token

↓

Backend

↓

Verify Token

↓

Generate JWT

↓

Return Access + Refresh

Access Token

30 Minutes

Refresh Token

7 Days

---

# Roles

Admin

Responsible for

- User Management
- Roles
- Holidays
- Leave Approval
- Settings

Project Manager

Responsible for

- Clients
- Projects
- Assignments
- Weekend Approval
- Reports

Account Manager

Responsible for

- Financial Dashboard
- Reports

Employee

Responsible for

- Timesheets
- Leave Requests
- Weekend Requests

---

# Core Business Rules

These rules are absolute.

1.

Daily Hours <= 8

2.

Weekly Target = 40 Hours

3.

Every Timesheet requires

- Project
- Hours
- Billable
- Task Description
- Work Summary

4.

Users cannot self register.

Admin creates users first.

5.

Soft Delete only.

Never hard delete users.

6.

Server validation is mandatory.

Never trust frontend.

7.

Timesheets DO NOT require approval.

8.

Leave Requests are approved only by Admin.

9.

Weekend Work is approved only by Project Manager.

---

# Database

Database

PostgreSQL

ORM

SQLAlchemy Async

Migration

Alembic

Never write raw SQL unless absolutely necessary.

Always use AsyncSession.

---

# API Rules

Base URL

/api/v1

Response

{
  "success": true,
  "message": "...",
  "data": {},
  "errors": null
}

Pagination

?page=1&limit=20

Authentication

Authorization: Bearer <token>

URL Style

kebab-case

Examples

leave-requests

weekend-work

Fields

snake_case

Example

project_manager_id

leave_type_id

---

# Modules

Current modules

- Auth
- Users
- Roles
- Clients
- Projects
- Project Assignments
- Timesheets
- Leave Types
- Leave Balances
- Leave Requests
- Holidays
- Tools
- Tool Allocations
- Weekend Work
- Dashboard
- Reports
- Settings
- System

Implement one module completely before starting another.

---

# API Development Rules

For every endpoint implement

Router

↓

Schema

↓

Validator

↓

Service

↓

Repository

↓

Tests

No shortcuts.

---

# Repository Rules

Repository contains

- Create
- Update
- Delete
- List
- Get By Id
- Exists
- Filters

Nothing else.

---

# Service Rules

Business logic belongs here.

Examples

Validate daily hours

Calculate weekly hours

Permission checks

Conflict detection

Leave balance checks

Duplicate validation

Project assignment validation

Never place these in repository.

---

# Error Handling

Use custom exceptions.

Always return meaningful messages.

Use proper status codes.

400

Validation

401

Unauthorized

403

Forbidden

404

Not Found

409

Conflict

422

Validation Error

500

Unexpected Error

---

# Coding Style

Use

Type Hints

Docstrings

Async functions

Dependency Injection

Clean architecture

Readable variable names

Never

Magic Numbers

Duplicate Logic

Long Functions

Large Routers

Business Logic inside Routers

---

# Security

Validate every request.

Check permissions before business logic.

Use JWT dependencies.

Never expose internal errors.

Never expose stack traces.

---

# Performance

Prefer joins over repeated queries.

Avoid N+1 queries.

Use pagination.

Select only required columns.

Batch operations where possible.

---

# Testing

Every module should contain

- Happy Path
- Permission Tests
- Validation Tests
- Edge Cases

---

# Git Workflow

Main

Production

Dev

Integration

Feature Branch

feature/<module>

Example

feature/auth

feature/users

feature/timesheets

Never commit directly to main.

Never commit directly to dev.

Always use Pull Requests.

---

# AI Development Workflow

Whenever implementing a feature

Step 1

Read business rules.

Step 2

Read schema.

Step 3

Implement repository.

Step 4

Implement service.

Step 5

Implement router.

Step 6

Add validation.

Step 7

Test manually.

Step 8

Write migration if required.

Step 9

Update API documentation.

Never skip steps.

---

# Current API Contract

The backend exposes approximately 63 REST endpoints across 17 modules.

Modules include

- Authentication
- Users
- Roles
- Clients
- Projects
- Project Assignments
- Timesheets
- Leave Types
- Leave Balances
- Leave Requests
- Holidays
- Tools
- Weekend Work
- Dashboard
- Reports
- Settings
- System

This API contract is the single source of truth.

Any backend implementation must remain compatible with the frontend contract unless explicitly changed.

---

# AI Rules

Always

✔ Follow Modular Monolith

✔ Use async SQLAlchemy

✔ Use Pydantic v2

✔ Follow Service → Repository pattern

✔ Keep business logic inside services

✔ Use Alembic for schema changes

✔ Write production-ready code

✔ Keep code simple and maintainable

Never

✘ Invent endpoints

✘ Change API contracts

✘ Break folder structure

✘ Ignore business rules

✘ Mix architecture layers

✘ Write temporary hacks

✘ Add unnecessary abstractions

✘ Over-engineer the MVP

The priority is maintainability, readability, consistency, and production readiness.