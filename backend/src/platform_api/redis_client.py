from collections.abc import AsyncIterator
from functools import lru_cache

from redis.asyncio import Redis

from platform_api.config import get_settings
from platform_api.observability import increment, set_gauge


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_cache_timeout_seconds,
        socket_timeout=settings.redis_cache_timeout_seconds,
        max_connections=settings.redis_max_connections,
        health_check_interval=30,
    )


async def get_redis() -> AsyncIterator[Redis]:
    yield get_redis_client()


async def close_redis_client() -> None:
    if get_redis_client.cache_info().currsize:
        await get_redis_client().aclose()
        get_redis_client.cache_clear()


_last_redis_run_id: str | None = None


def record_redis_server_metrics(info: dict[str, object]) -> None:
    global _last_redis_run_id
    metric_fields = {
        "connected_clients": "redis.server.connected_clients",
        "used_memory": "redis.server.used_memory_bytes",
        "evicted_keys": "redis.server.evicted_keys_total",
        "keyspace_hits": "redis.server.keyspace_hits_total",
        "keyspace_misses": "redis.server.keyspace_misses_total",
        "uptime_in_seconds": "redis.server.uptime_seconds",
        "instantaneous_ops_per_sec": "redis.server.ops_per_second",
    }
    for field, metric in metric_fields.items():
        value = info.get(field)
        if isinstance(value, int):
            set_gauge(metric, value)

    run_id = info.get("run_id")
    if isinstance(run_id, str):
        if _last_redis_run_id is not None and _last_redis_run_id != run_id:
            increment("redis.server.failovers")
        _last_redis_run_id = run_id
