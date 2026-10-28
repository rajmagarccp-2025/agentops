from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.observability import increment
from platform_api.redis_client import get_redis, record_redis_server_metrics
from platform_api.workflow_queue import workflow_queue

router = APIRouter(prefix="/health", tags=["health"])


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, str]


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    db: Annotated[Session, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ReadinessResponse:
    dependencies: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception:
        dependencies["database"] = "unavailable"

    try:
        await redis.ping()
        dependencies["redis"] = "ok"
        try:
            record_redis_server_metrics(await redis.info())
        except (RedisError, AttributeError):
            increment("redis.server.metrics_errors")
    except Exception:
        dependencies["redis"] = "unavailable"

    try:
        workers = workflow_queue.worker_summary()
        dependencies["workflow_worker"] = (
            "ok" if workers["workers_online"] > 0 else "unavailable"
        )
    except Exception:
        dependencies["workflow_worker"] = "unavailable"

    status = "ok" if all(value == "ok" for value in dependencies.values()) else "degraded"
    return ReadinessResponse(status=status, dependencies=dependencies)
