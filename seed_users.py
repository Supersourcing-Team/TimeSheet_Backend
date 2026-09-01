"""
Database seeding script.

Run this ONCE after setting up a fresh database to populate required roles
and create the initial Admin user account.

Usage:
    python seed_users.py

Before running:
    1. Copy .env.example -> .env
    2. Set ADMIN_EMAIL in your .env to your own work email address.
    3. Ensure the database is reachable and migrations have been applied:
           alembic upgrade head
"""

import asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.role import Role
from app.models.user import User


# ---------------------------------------------------------------------------
# Roles – these are always seeded and must not be changed.
# ---------------------------------------------------------------------------
SEED_ROLES = [
    {"name": "Admin", "description": "System Administrator"},
    {"name": "Project_Manager", "description": "Project Manager"},
    {"name": "Account_Manager", "description": "Account Manager"},
    {"name": "Employee", "description": "Software Engineer / Employee"},
]


# ---------------------------------------------------------------------------
# Default admin user – only the email comes from the environment.
# ---------------------------------------------------------------------------
DEFAULT_ADMIN = {
    "email": settings.ADMIN_EMAIL,   # <-- set ADMIN_EMAIL in your .env
    "first_name": "Admin",
    "last_name": "User",
    "role_name": "Admin",
    "employee_id": "EMP-ADM-001",
}


async def seed():
    # Ensure all tables exist (safe if they already do)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ------------------------------------------------------------------
        # 1. Seed Roles
        # ------------------------------------------------------------------
        role_map: dict[str, int] = {}
        for rdata in SEED_ROLES:
            res = await session.execute(
                select(Role).filter(Role.name == rdata["name"])
            )
            existing_role = res.scalar_one_or_none()
            if not existing_role:
                new_role = Role(name=rdata["name"], description=rdata["description"])
                session.add(new_role)
                await session.flush()
                role_map[rdata["name"]] = new_role.id
                print(f"  [+] Created role: {rdata['name']}")
            else:
                role_map[rdata["name"]] = existing_role.id
                print(f"  [=] Role already exists: {rdata['name']}")

        # ------------------------------------------------------------------
        # 2. Seed default Admin user
        # ------------------------------------------------------------------
        udata = DEFAULT_ADMIN
        admin_email = udata["email"]

        if admin_email == "admin@yourcompany.com":
            print(
                "\n  [!] WARNING: ADMIN_EMAIL is still the placeholder value.\n"
                "      Set ADMIN_EMAIL in your .env to your real work email,\n"
                "      then re-run this script.\n"
            )

        res = await session.execute(
            select(User).filter(User.email == admin_email)
        )
        existing_user = res.scalar_one_or_none()
        role_id = role_map[udata["role_name"]]

        if not existing_user:
            new_user = User(
                email=admin_email,
                first_name=udata["first_name"],
                last_name=udata["last_name"],
                employee_id=udata["employee_id"],
                role_id=role_id,
                status="Active",
            )
            session.add(new_user)
            print(f"\n  [+] Created default Admin user: {admin_email}")
        else:
            # Keep the admin role in sync in case it was changed manually
            existing_user.role_id = role_id
            existing_user.status = "Active"
            print(f"\n  [=] Admin user already exists, ensured role/status: {admin_email}")

        await session.commit()

    print("\n✅  Database seeding completed successfully!")
    print(f"    Admin email : {admin_email}")
    print(
        "    Next step   : Ask the admin to log in via Google OAuth "
        "using the above email to start the onboarding flow."
    )


if __name__ == "__main__":
    asyncio.run(seed())
