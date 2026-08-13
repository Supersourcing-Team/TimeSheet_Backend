import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:admin@localhost:5432/timesheet_db')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(text('SELECT count(*) FROM holidays'))
        print('Holidays Count:', result.scalar())
        result = await db.execute(text('SELECT count(*) FROM leave_types'))
        print('Leave Types Count:', result.scalar())

asyncio.run(main())
