from typing import Any, Generic, Optional, TypeVar

from fastapi import status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized API Response wrapper structure."""

    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[T] = None
    errors: Optional[Any] = None


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """Returns a standardized JSONResponse for successful operations."""
    payload = {
        "success": True,
        "message": message,
        "data": data,
        "errors": None,
    }
    return JSONResponse(status_code=status_code, content=payload)


def created_response(
    data: Any = None,
    message: str = "Resource created successfully",
) -> JSONResponse:
    """Returns a 201 Created standardized JSONResponse."""
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def error_response(
    message: str = "An error occurred",
    errors: Any = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    """Returns a standardized JSONResponse for error scenarios."""
    payload = {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors,
    }
    return JSONResponse(status_code=status_code, content=payload)
