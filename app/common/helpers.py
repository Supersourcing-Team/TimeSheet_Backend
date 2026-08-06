from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple


def is_weekend(target_date: date) -> bool:
    """Checks if a given date falls on a weekend (Saturday=5, Sunday=6)."""
    return target_date.weekday() >= 5


def get_week_start_and_end_dates(target_date: date) -> Tuple[date, date]:
    """
    Returns the Monday (start) and Sunday (end) dates for the week containing target_date.
    """
    start_of_week = target_date - timedelta(days=target_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week


def calculate_working_days(
    start_date: date,
    end_date: date,
    holidays: Optional[List[date]] = None,
) -> int:
    """
    Calculates net working days between start_date and end_date (inclusive),
    excluding weekends and company holidays.
    """
    if start_date > end_date:
        return 0

    holiday_set = set(holidays) if holidays else set()
    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        if not is_weekend(current_date) and current_date not in holiday_set:
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


def validate_daily_hours(
    existing_hours: float,
    new_hours: float,
    max_daily_hours: float = 8.0,
) -> bool:
    """
    Validates if adding new_hours to existing_hours respects the maximum 8 hours daily cap.
    """
    return (existing_hours + new_hours) <= max_daily_hours


def validate_weekly_hours(
    total_weekly_hours: float,
    max_weekly_hours: float = 40.0,
) -> bool:
    """
    Validates if total weekly hours align with the 40-hour target limit.
    """
    return total_weekly_hours <= max_weekly_hours


def calculate_project_profit(
    revenue: float,
    tools_cost: float,
    billable_hours_cost: float,
) -> float:
    """
    Calculates project profit based on Critical Business Rule 5:
    Profit = Revenue - (Tools Cost + Billable Hours Cost)
    """
    return round(revenue - (tools_cost + billable_hours_cost), 2)


def format_date(target: Optional[date | datetime], fmt: str = "%Y-%m-%d") -> str:
    """Formats a date or datetime object into a standardized string."""
    if not target:
        return ""
    return target.strftime(fmt)
