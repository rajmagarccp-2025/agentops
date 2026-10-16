from typing import Annotated

from fastapi import APIRouter, Depends

from platform_api.inventory.schemas import InventoryResource
from platform_api.inventory.service import inventory_repository
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/resources", response_model=list[InventoryResource])
async def list_resources(
    principal: Annotated[Principal, Depends(require_permission("inventory:read"))],
) -> list[InventoryResource]:
    return inventory_repository.list_for_tenant(principal.tenant_id)
