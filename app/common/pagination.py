import math
from typing import Any, Generic, List, Optional, TypeVar

from fastapi import Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams:
    """Dependency model for standard query pagination parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number starting from 1"),
        limit: int = Query(20, ge=1, le=100, description="Number of items per page (max 100)"),
    ):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        """Calculates SQL offset for DB queries."""
        return (self.page - 1) * self.limit


class PaginatedData(BaseModel, Generic[T]):
    """Structure for paginated data content."""

    total: int = Field(..., description="Total number of items available")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total available pages")
    items: List[T] = Field(default_factory=list, description="List of items for current page")


class PaginatedAPIResponse(BaseModel, Generic[T]):
    """Standardized API response structure for paginated endpoints."""

    success: bool = True
    message: str = "Data retrieved successfully"
    data: PaginatedData[T]
    errors: Optional[Any] = None


def create_pagination_data(items: List[Any], total: int, page: int, limit: int) -> dict:
    """Builds a dictionary of paginated metadata and items."""
    limit = max(1, limit)
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "items": items,
    }


def create_paginated_response(
    items: List[Any],
    total: int,
    page: int,
    limit: int,
    message: str = "Data retrieved successfully",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """Builds a standardized paginated JSONResponse."""
    paginated_data = create_pagination_data(items, total, page, limit)

    payload = {
        "success": True,
        "message": message,
        "data": paginated_data,
        "errors": None,
    }

    return JSONResponse(status_code=status_code, content=payload)

