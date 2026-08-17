from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.system_settings import SystemSettings
from app.modules.settings.schema import SystemSettingsUpdate

class SystemSettingsRepository:
    @staticmethod
    async def get_settings(db: AsyncSession) -> Optional[SystemSettings]:
        result = await db.execute(select(SystemSettings).order_by(SystemSettings.id.desc()).limit(1))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_settings(db: AsyncSession, update_data: SystemSettingsUpdate) -> SystemSettings:
        settings = await SystemSettingsRepository.get_settings(db)
        if not settings:
            # create default
            settings = SystemSettings(**update_data.model_dump())
            db.add(settings)
        else:
            for key, value in update_data.model_dump().items():
                setattr(settings, key, value)
        await db.commit()
        await db.refresh(settings)
        return settings
