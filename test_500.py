import asyncio
from app.core.database import get_db
from app.modules.leave_requests.service import LeaveRequestService
from app.models.user import User
from app.modules.leave_requests.schema import LeaveRequestResponse

async def main():
    async for db in get_db():
        from sqlalchemy.future import select
        res = await db.execute(select(User).where(User.role_id == 2)) # Try finding a PM (role_id 2 or similar)
        pm = res.scalars().first()
        if not pm:
            res = await db.execute(select(User))
            pm = res.scalars().first()

        print(f"Using user {pm.id}")
        leaves = await LeaveRequestService.get_upcoming_team_leaves(db, pm)
        print(f"Leaves found: {len(leaves)}")
        for l in leaves:
            try:
                LeaveRequestResponse.model_validate(l)
            except Exception as e:
                print(f"Validation failed for leaf {l.id}: {e}")
        break

if __name__ == '__main__':
    asyncio.run(main())
