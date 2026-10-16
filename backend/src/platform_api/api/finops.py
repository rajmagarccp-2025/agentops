from typing import Annotated

from fastapi import APIRouter, Depends

from platform_api.finops.schemas import (
    CostRecord,
    CostRecordCreate,
    FinOpsRecommendation,
    FinOpsSummary,
    UtilizationCreate,
    UtilizationRecord,
)
from platform_api.finops.service import (
    build_recommendations,
    ingest_cost,
    ingest_utilization,
    summarize,
)
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/finops", tags=["finops"])


@router.post("/costs", response_model=CostRecord)
async def create_cost_record(
    body: CostRecordCreate,
    principal: Annotated[Principal, Depends(require_permission("finops:write"))],
) -> CostRecord:
    return ingest_cost(principal.tenant_id, body)


@router.post("/utilization", response_model=UtilizationRecord)
async def create_utilization_record(
    body: UtilizationCreate,
    principal: Annotated[Principal, Depends(require_permission("finops:write"))],
) -> UtilizationRecord:
    return ingest_utilization(principal.tenant_id, body)


@router.get("/recommendations", response_model=list[FinOpsRecommendation])
async def recommendations(
    principal: Annotated[Principal, Depends(require_permission("finops:read"))],
) -> list[FinOpsRecommendation]:
    return build_recommendations(principal.tenant_id)


@router.get("/summary", response_model=FinOpsSummary)
async def summary(
    principal: Annotated[Principal, Depends(require_permission("finops:read"))],
) -> FinOpsSummary:
    return summarize(principal.tenant_id)
