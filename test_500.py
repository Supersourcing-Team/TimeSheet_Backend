import asyncio
from app.core.database import get_db
from app.models.user import User
from app.core.security import create_access_token
import requests

async def main():
    async for db in get_db():
        from sqlalchemy.future import select
        res = await db.execute(select(User).where(User.email == 'balram6604@gmail.com'))
        admin = res.scalars().first()
        token = create_access_token({"sub": str(admin.id)})
        print(f"Generated token for Admin")
        
        # Test endpoint
        res = requests.get("http://127.0.0.1:8000/api/v1/leave-requests/upcoming", headers={"Authorization": f"Bearer {token}"})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
        break

if __name__ == '__main__':
    asyncio.run(main())
