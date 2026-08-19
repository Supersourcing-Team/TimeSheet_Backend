import os
import sys
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def main():
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE projects ADD COLUMN hourly_rate DOUBLE PRECISION"))
            print("Added hourly_rate column")
        except Exception as e:
            print(f"Error adding hourly_rate: {e}")
            
        try:
            await conn.execute(text("ALTER TABLE projects ADD COLUMN allocated_hours DOUBLE PRECISION"))
            print("Added allocated_hours column")
        except Exception as e:
            print(f"Error adding allocated_hours: {e}")
            
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
