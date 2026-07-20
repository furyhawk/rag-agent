"""Common API response schemas."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Standard success response envelope."""

    data: Any


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class PaginatedResponse(BaseModel):
    """Paginated list response."""

    items: list[Any]
    total: int
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
