from typing import Annotated

from fastapi import APIRouter, Depends

from platform_api.changes.repository import change_repository
from platform_api.changes.schemas import ChangeEvent, ChangeEventCreate
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/changes", tags=["changes"])


@router.post("", response_model=ChangeEvent)
async def ingest_change(
    body: ChangeEventCreate,
    principal: Annotated[Principal, Depends(require_permission("changes:write"))],
) -> ChangeEvent:
    return change_repository.create(principal.tenant_id, body)


@router.get("", response_model=list[ChangeEvent])
async def list_all_changes(
    principal: Annotated[Principal, Depends(require_permission("changes:read"))],
) -> list[ChangeEvent]:
    return change_repository.list_for_tenant(principal.tenant_id)


@router.get("/{service}", response_model=list[ChangeEvent])
async def list_changes(
    service: str,
    principal: Annotated[Principal, Depends(require_permission("changes:read"))],
) -> list[ChangeEvent]:
    return change_repository.list_for_service(principal.tenant_id, service)
