from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from platform_api.mcp.gateway import tool_registry
from platform_api.mcp.registry import (
    ToolAuthorizationError,
    ToolNotFoundError,
    ToolPolicyUnavailableError,
)
from platform_api.mcp.types import ToolCategory, ToolRequest, ToolRisk
from platform_api.security import Principal, get_current_principal, require_permission

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolSummary(BaseModel):
    name: str
    description: str
    category: ToolCategory
    risk: ToolRisk
    required_permission: str


class ToolExecutionResponse(BaseModel):
    execution_id: str
    status: str
    tool_name: str
    risk: ToolRisk
    tenant_id: str
    result: dict[str, object] | None = None
    validation_errors: list[dict[str, object]] | None = None


@router.get("", response_model=list[ToolSummary])
async def list_tools(
    _: Annotated[Principal, Depends(require_permission("tools:read"))],
) -> list[ToolSummary]:
    return [
        ToolSummary(
            name=tool.name,
            description=tool.description,
            category=tool.category,
            risk=tool.risk,
            required_permission=tool.required_permission,
        )
        for tool in tool_registry.list_tools()
    ]


@router.get("/{tool_name:path}", response_model=ToolSummary)
async def get_tool(
    tool_name: str,
    _: Annotated[Principal, Depends(require_permission("tools:read"))],
) -> ToolSummary:
    try:
        tool = tool_registry.get(tool_name)
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found") from exc
    return ToolSummary(
        name=tool.name,
        description=tool.description,
        category=tool.category,
        risk=tool.risk,
        required_permission=tool.required_permission,
    )


@router.post("/{tool_name:path}/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_name: str,
    request: Request,
    body: ToolRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ToolExecutionResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    try:
        execution = tool_registry.execute(
            tool_name,
            body.parameters,
            principal,
            request_id,
            body.dry_run,
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found") from exc
    except ToolAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing tool permission: {exc.args[0]}",
        ) from exc
    except ToolPolicyUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Policy decision service is unavailable; mutation was not executed.",
        ) from exc

    result = execution.result.data if execution.result is not None else None
    response = ToolExecutionResponse(
        execution_id=execution.execution_id,
        status=execution.status,
        tool_name=execution.tool_name,
        risk=execution.risk,
        tenant_id=execution.tenant_id,
        result=result,
        validation_errors=execution.validation_errors,
    )
    if execution.status == "validation_failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=response.model_dump(),
        )
    return response
