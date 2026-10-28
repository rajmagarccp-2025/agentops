from __future__ import annotations

from redis.exceptions import ConnectionError

from platform_api.observability import metrics_text
from platform_api.redis_client import record_redis_server_metrics
from platform_api.secrets.cache import SecretResolutionCache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.fail = False

    def get(self, key: str) -> str | None:
        if self.fail:
            raise ConnectionError("redis unavailable")
        return self.values.get(key)

    def set(self, key: str, value: str, *, ex: int) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.values[key] = value
        self.expirations[key] = ex

    def delete(self, key: str) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.values.pop(key, None)


def test_secret_cache_encrypts_and_separates_tenants() -> None:
    client = FakeRedis()
    cache = SecretResolutionCache(client, ttl_seconds=23, max_value_bytes=100)

    cache.set("tenant-a", "secret-1", "version-1", "plaintext-secret")

    cached_payload = next(iter(client.values.values()))
    assert "plaintext-secret" not in cached_payload
    assert "tenant-a" not in cached_payload
    assert next(iter(client.expirations.values())) == 23
    assert cache.get("tenant-a", "secret-1", "version-1") == "plaintext-secret"
    assert cache.get("tenant-b", "secret-1", "version-1") is None
    assert "tenant-a" not in metrics_text()
    assert "plaintext-secret" not in metrics_text()


def test_secret_cache_rejects_stale_version_and_supports_invalidation() -> None:
    client = FakeRedis()
    cache = SecretResolutionCache(client, ttl_seconds=30, max_value_bytes=100)
    cache.set("tenant", "secret", "version-1", "old-value")

    assert cache.get("tenant", "secret", "version-2") is None
    assert client.values == {}

    cache.set("tenant", "secret", "version-2", "new-value")
    cache.invalidate("tenant", "secret")
    assert cache.get("tenant", "secret", "version-2") is None


def test_secret_cache_bypasses_oversized_values() -> None:
    client = FakeRedis()
    cache = SecretResolutionCache(client, ttl_seconds=30, max_value_bytes=4)

    cache.set("tenant", "secret", "version-1", "too-large")

    assert client.values == {}


def test_secret_cache_fails_open_when_redis_is_unavailable() -> None:
    client = FakeRedis()
    client.fail = True
    cache = SecretResolutionCache(client, ttl_seconds=30, max_value_bytes=100)

    assert cache.get("tenant", "secret", "version-1") is None
    cache.set("tenant", "secret", "version-1", "provider-value")
    cache.invalidate("tenant", "secret")


def test_redis_server_metrics_record_gauges_and_run_id_changes(monkeypatch) -> None:
    import platform_api.redis_client as redis_client

    monkeypatch.setattr(redis_client, "_last_redis_run_id", None)
    record_redis_server_metrics(
        {
            "connected_clients": 2,
            "used_memory": 4096,
            "evicted_keys": 1,
            "keyspace_hits": 3,
            "keyspace_misses": 4,
            "uptime_in_seconds": 500,
            "instantaneous_ops_per_sec": 6,
            "run_id": "first",
        }
    )
    record_redis_server_metrics({"run_id": "second"})

    text = metrics_text()
    assert "platform_redis_server_connected_clients 2" in text
    assert "platform_redis_server_used_memory_bytes 4096" in text
    assert "platform_redis_server_failovers 1" in text
