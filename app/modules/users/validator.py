from fastapi import HTTPException, status

ALLOWED_STATUSES = {"Active", "Inactive"}


class UserValidator:
    """Validator class for complex User validations."""

    @staticmethod
    def validate_status(user_status: str) -> str:
        formatted = user_status.strip().capitalize()
        if formatted not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{user_status}'. Must be one of: {', '.join(sorted(ALLOWED_STATUSES))}.",
            )
        return formatted
