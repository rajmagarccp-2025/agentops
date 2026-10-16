from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from platform_api.observability import metrics_snapshot, metrics_text
from platform_api.security import Principal, require_permission
from platform_api.workflow_queue import workflow_queue

router = APIRouter(tags=["observability"])


class ObservabilityMetricsResponse(BaseModel):
    scope: Literal["process_and_database"] = "process_and_database"
    snapshot_at: datetime
    metrics: dict[str, int]


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics_text(), media_type="text/plain; version=0.0.4")


@router.get("/observability/metrics", response_model=ObservabilityMetricsResponse)
async def observability_metrics(
    _: Annotated[Principal, Depends(require_permission("observability:read"))],
) -> ObservabilityMetricsResponse:
    metrics = metrics_snapshot()
    for status, count in workflow_queue.summary().items():
        metrics[f"workflow_jobs_{status}"] = count
    metrics.update(workflow_queue.worker_summary())
    return ObservabilityMetricsResponse(
        scope="process_and_database",
        snapshot_at=datetime.now(UTC),
        metrics=metrics,
    )
