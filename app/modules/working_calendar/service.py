from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.working_calendar.model import WorkingCalendar
from app.modules.working_calendar.repository import WorkingCalendarRepository
from app.modules.working_calendar.schema import WorkingCalendarUpdate

class WorkingCalendarService:
    @staticmethod
    async def get_config(db: AsyncSession) -> WorkingCalendar:
        config = await WorkingCalendarRepository.get_config(db)
        if not config:
            config = await WorkingCalendarRepository.create(db)
        return config

    @staticmethod
    async def update_config(db: AsyncSession, data: WorkingCalendarUpdate) -> WorkingCalendar:
        config = await WorkingCalendarService.get_config(db)
        return await WorkingCalendarRepository.update(db, config, **data.model_dump(exclude_unset=True))
