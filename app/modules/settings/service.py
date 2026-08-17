from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.settings.repository import SystemSettingsRepository
from app.modules.settings.schema import SystemSettingsSchema, SystemSettingsUpdate

class SystemSettingsService:
    @staticmethod
    async def get_settings(db: AsyncSession) -> SystemSettingsSchema:
        settings = await SystemSettingsRepository.get_settings(db)
        if not settings:
            # Return some defaults if none exist
            return SystemSettingsSchema(
                org_name="SuperTime Enterprise",
                org_reg_id=None,
                contact_email="admin@supertime.com",
                company_logo_url=None,
                time_zone="Asia/Kolkata (IST UTC+05:30)",
                email_notifications=True,
                timesheet_approval_reminders=True,
                leave_request_alerts=True,
                primary_color="#2563eb"
            )
        return SystemSettingsSchema.model_validate(settings)

    @staticmethod
    async def update_settings(db: AsyncSession, data: SystemSettingsUpdate) -> SystemSettingsSchema:
        settings = await SystemSettingsRepository.update_settings(db, data)
        return SystemSettingsSchema.model_validate(settings)
