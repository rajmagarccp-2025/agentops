"""MCP Gateway types and contracts re-exported from platform_api.contracts.mcp."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from platform_api.contracts.mcp import (
    ToolCategory,
    ToolRequest,
    ToolResponse,
    ToolRisk,
    ToolSpec,
)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    data: dict[str, Any]


ToolHandler = Callable[[Any, str], ToolResult]

__all__ = [
    "ToolCategory",
    "ToolHandler",
    "ToolRequest",
    "ToolResponse",
    "ToolResult",
    "ToolRisk",
    "ToolSpec",
]
