from pydantic import BaseModel
from typing import Optional

class SystemSettingsSchema(BaseModel):
    org_name: str
    org_reg_id: Optional[str] = None
    contact_email: str
    company_logo_url: Optional[str] = None
    time_zone: str
    email_notifications: bool
    timesheet_approval_reminders: bool
    leave_request_alerts: bool
    primary_color: str

    class Config:
        from_attributes = True

class SystemSettingsCreate(SystemSettingsSchema):
    pass

class SystemSettingsUpdate(SystemSettingsSchema):
    pass
