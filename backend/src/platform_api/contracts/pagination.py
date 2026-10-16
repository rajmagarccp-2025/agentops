"""Pagination and filtering query response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = Field(default=None, max_length=100)
    sort_order: Literal["asc", "desc"] = "asc"


class PaginatedResponse[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    has_next: bool
    has_prev: bool
