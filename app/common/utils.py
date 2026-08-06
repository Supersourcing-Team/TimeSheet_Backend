import re
import secrets
import string
from datetime import date, datetime
from typing import Optional


def generate_random_string(length: int = 12) -> str:
    """Generates a secure random alphanumeric string."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def slugify(text: str) -> str:
    """Converts string into clean URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def sanitize_filename(filename: str) -> str:
    """Sanitizes user uploaded filename to prevent directory traversal / invalid characters."""
    clean_name = re.sub(r"[^\w\.-]", "_", filename)
    return clean_name.lstrip(".")


def mask_email(email: str) -> str:
    """Masks email address for display/privacy (e.g. j***n@example.com)."""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def parse_date_safe(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[date]:
    """Safely parses a date string, returning None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), fmt).date()
    except ValueError:
        return None
