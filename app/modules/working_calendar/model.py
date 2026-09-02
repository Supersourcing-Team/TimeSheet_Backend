from sqlalchemy import Column, Integer, Float, String, JSON
from app.core.database import Base

class WorkingCalendar(Base):
    __tablename__ = "working_calendar"

    id = Column(Integer, primary_key=True, index=True)
    full_day_hours = Column(Float, default=8.0, nullable=False)
    half_day_hours = Column(Float, default=4.0, nullable=False)
    partial_day_min_hours = Column(Float, default=1.0, nullable=False)
    partial_day_max_hours = Column(Float, default=7.5, nullable=False)
    working_days = Column(
        JSON,
        default={
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": True,
            "saturday": False,
            "sunday": False,
        },
        nullable=False,
    )
    time_zone = Column(String, default="UTC", nullable=False)
