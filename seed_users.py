import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine, Base
from app.models.role import Role
from app.models.user import User

SEED_ROLES = [
    {"name": "Admin", "description": "System Administrator"},
    {"name": "Project_Manager", "description": "Project Manager"},
    {"name": "Account_Manager", "description": "Account Manager"},
    {"name": "Employee", "description": "Software Engineer / Employee"},
]

SEED_USERS = [
    {
        "email": "balram6604@gmail.com",
        "first_name": "Balram",
        "last_name": "Admin",
        "role_name": "Admin",
        "employee_id": "EMP-ADM-001",
    },
    {
        "email": "balramprajapati3263@gmail.com",
        "first_name": "Balram",
        "last_name": "PM",
        "role_name": "Project_Manager",
        "employee_id": "EMP-PM-002",
    },
    {
        "email": "balram.btech@gmail.com",
        "first_name": "Balram",
        "last_name": "Employee",
        "role_name": "Employee",
        "employee_id": "EMP-DEV-003",
    },
    {
        "email": "balram@supersourcing.com",
        "first_name": "Balram",
        "last_name": "Account Manager",
        "role_name": "Account_Manager",
        "employee_id": "EMP-AM-004",
    },
]

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Seed Roles
        role_map = {}
        for rdata in SEED_ROLES:
            res = await session.execute(select(Role).filter(Role.name == rdata["name"]))
            existing_role = res.scalar_one_or_none()
            if not existing_role:
                new_role = Role(name=rdata["name"], description=rdata["description"])
                session.add(new_role)
                await session.flush()
                role_map[rdata["name"]] = new_role.id
                print(f"Created Role: {rdata['name']}")
            else:
                role_map[rdata["name"]] = existing_role.id
                print(f"Existing Role: {rdata['name']}")

        # Seed Users
        for udata in SEED_USERS:
            res = await session.execute(select(User).filter(User.email == udata["email"]))
            existing_user = res.scalar_one_or_none()
            role_id = role_map[udata["role_name"]]

            if not existing_user:
                new_user = User(
                    email=udata["email"],
                    first_name=udata["first_name"],
                    last_name=udata["last_name"],
                    employee_id=udata["employee_id"],
                    role_id=role_id,
                    status="Active",
                )
                session.add(new_user)
                print(f"Added User: {udata['email']} as {udata['role_name']}")
            else:
                existing_user.role_id = role_id
                existing_user.status = "Active"
                print(f"Updated User: {udata['email']} role to {udata['role_name']}")

        await session.commit()
        print("\nDatabase Seeding Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
