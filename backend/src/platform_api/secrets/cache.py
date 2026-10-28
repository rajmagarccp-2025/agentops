from __future__ import annotations

import hashlib
import json
import logging
import time
from binascii import Error as BinasciiError
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidTag
from redis import Redis
from redis.exceptions import RedisError

from platform_api.config import get_settings
from platform_api.observability import increment
from platform_api.secrets.crypto import InternalCryptoService

_logger = logging.getLogger(__name__)
_CACHE_SCHEMA_VERSION = 1
_CACHE_KEY_PREFIX = "agentops:secret-resolution:v1:"
_CACHE_SERIALIZATION_OVERHEAD_BYTES = 1_024


@lru_cache(maxsize=1)
def get_cache_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_cache_timeout_seconds,
        socket_timeout=settings.redis_cache_timeout_seconds,
        max_connections=settings.redis_cache_max_connections,
        health_check_interval=30,
    )


def close_cache_client() -> None:
    if get_cache_client.cache_info().currsize:
        get_cache_client().close()
        get_cache_client.cache_clear()
    get_secret_resolution_cache.cache_clear()


def _cache_key(tenant_id: str, secret_id: str) -> str:
    scope_hash = hashlib.sha256(f"{tenant_id}\0{secret_id}".encode()).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{scope_hash}"


class SecretResolutionCache:
    """Disposable encrypted cache for already-authorized secret resolutions."""

    def __init__(
        self,
        client: Any,
        ttl_seconds: int,
        max_value_bytes: int,
    ) -> None:
        if ttl_seconds < 1 or max_value_bytes < 1:
            raise ValueError("Cache TTL and maximum value size must be positive")
        self._client = client
        self._ttl_seconds = ttl_seconds
        self._max_value_bytes = max_value_bytes

    def get(self, tenant_id: str, secret_id: str, version_id: str) -> str | None:
        key = _cache_key(tenant_id, secret_id)
        started = time.perf_counter()
        try:
            serialized = self._client.get(key)
            if serialized is None:
                self._record_operation("miss", started)
                return None
            if not isinstance(serialized, str):
                raise ValueError("Cache payload has an invalid encoding")
            if len(serialized.encode("utf-8")) > (
                self._max_value_bytes * 2 + _CACHE_SERIALIZATION_OVERHEAD_BYTES
            ):
                self._client.delete(key)
                increment("redis.secret_cache.errors")
                return None
            entry = json.loads(serialized)
            if (
                not isinstance(entry, dict)
                or entry.get("schema_version") != _CACHE_SCHEMA_VERSION
                or entry.get("version_id") != version_id
                or not isinstance(entry.get("ciphertext"), str)
                or not isinstance(entry.get("encryption_metadata"), dict)
            ):
                self._client.delete(key)
                self._record_operation("miss", started)
                return None
            value = InternalCryptoService.decrypt(
                entry["ciphertext"], entry["encryption_metadata"]
            )
            if len(value.encode("utf-8")) > self._max_value_bytes:
                self._client.delete(key)
                increment("redis.secret_cache.errors")
                return None
            self._record_operation("hit", started)
            return value
        except (
            RedisError,
            ValueError,
            TypeError,
            KeyError,
            InvalidTag,
            BinasciiError,
        ):
            self._record_error(started)
            return None

    def set(
        self,
        tenant_id: str,
        secret_id: str,
        version_id: str,
        value: str,
    ) -> None:
        if len(value.encode("utf-8")) > self._max_value_bytes:
            increment("redis.secret_cache.skipped_oversize")
            return
        try:
            ciphertext, encryption_metadata = InternalCryptoService.encrypt(value)
            serialized = json.dumps(
                {
                    "schema_version": _CACHE_SCHEMA_VERSION,
                    "version_id": version_id,
                    "ciphertext": ciphertext,
                    "encryption_metadata": encryption_metadata,
                },
                separators=(",", ":"),
            )
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, BinasciiError, InvalidTag):
            increment("redis.secret_cache.errors")
            _logger.warning("Redis secret cache encryption failed; continuing without cache")
            return
        if len(serialized.encode("utf-8")) > (
            self._max_value_bytes * 2 + _CACHE_SERIALIZATION_OVERHEAD_BYTES
        ):
            increment("redis.secret_cache.skipped_oversize")
            return

        started = time.perf_counter()
        try:
            self._client.set(
                _cache_key(tenant_id, secret_id),
                serialized,
                ex=self._ttl_seconds,
            )
            self._record_operation("writes", started)
        except RedisError:
            self._record_error(started)

    def invalidate(self, tenant_id: str, secret_id: str) -> None:
        started = time.perf_counter()
        try:
            self._client.delete(_cache_key(tenant_id, secret_id))
            self._record_operation("invalidations", started)
        except RedisError:
            self._record_error(started)

    @staticmethod
    def _record_operation(operation: str, started: float) -> None:
        increment(f"redis.secret_cache.{operation}")
        increment(
            "redis.secret_cache.latency_ms",
            int((time.perf_counter() - started) * 1_000),
        )

    @staticmethod
    def _record_error(started: float) -> None:
        increment("redis.secret_cache.errors")
        increment(
            "redis.secret_cache.latency_ms",
            int((time.perf_counter() - started) * 1_000),
        )
        _logger.warning("Redis secret cache operation failed; continuing without cache")


@lru_cache(maxsize=1)
def get_secret_resolution_cache() -> SecretResolutionCache:
    settings = get_settings()
    return SecretResolutionCache(
        client=get_cache_client(),
        ttl_seconds=settings.secret_cache_ttl_seconds,
        max_value_bytes=settings.secret_cache_max_value_bytes,
    )
