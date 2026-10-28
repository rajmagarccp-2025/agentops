from typing import cast

import pytest
from redis import Redis
from redis.exceptions import RedisError

from platform_api.llm.quota import (
    _RELEASE_SCRIPT,
    _RESERVE_SCRIPT,
    _SETTLE_SCRIPT,
    RedisTenantQuota,
    TenantQuotaUnavailable,
    TenantRateLimitExceeded,
    TenantTokenBudgetExceeded,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.keys: list[str] = []
        self.fail = False

    def eval(self, script: str, numkeys: int, *args: str | int) -> int:
        if self.fail:
            raise RedisError("offline")
        self.keys.extend(str(value) for value in args[:numkeys])
        if script == _RESERVE_SCRIPT:
            minute_key, daily_key = str(args[0]), str(args[1])
            requests_limit, daily_limit, tokens = map(int, args[2:5])
            requests = self.values.get(minute_key, 0) + 1
            self.values[minute_key] = requests
            if requests > requests_limit:
                self.values[minute_key] -= 1
                return 0
            used = self.values.get(daily_key, 0)
            if used + tokens > daily_limit:
                self.values[minute_key] -= 1
                return -1
            self.values[daily_key] = used + tokens
            return 1
        if script in {_SETTLE_SCRIPT, _RELEASE_SCRIPT}:
            daily_key = str(args[0])
            used = self.values.get(daily_key, 0)
            reserved = int(args[1])
            actual = int(args[2]) if script == _SETTLE_SCRIPT else 0
            self.values[daily_key] = max(0, used - reserved + actual)
            return self.values[daily_key]
        raise AssertionError("Unexpected Redis script")


def test_redis_quota_reserve_settle_and_release() -> None:
    redis = FakeRedis()
    quota = RedisTenantQuota(cast(Redis, redis), requests_per_minute=10, daily_token_budget=20)

    quota.reserve("tenant-private-id", 8)
    daily_key = next(key for key in redis.values if ":tokens:" in key)
    assert redis.values[daily_key] == 8
    assert "tenant-private-id" not in " ".join(redis.keys)

    quota.settle("tenant-private-id", reserved_tokens=8, actual_tokens=5)
    assert redis.values[daily_key] == 5
    quota.reserve("tenant-private-id", 4)
    quota.release("tenant-private-id", reserved_tokens=4)
    assert redis.values[daily_key] == 5


def test_redis_quota_enforces_request_and_daily_limits() -> None:
    redis = FakeRedis()
    quota = RedisTenantQuota(cast(Redis, redis), requests_per_minute=1, daily_token_budget=10)
    quota.reserve("tenant-a", 4)
    with pytest.raises(TenantRateLimitExceeded):
        quota.reserve("tenant-a", 1)

    other_tenant_quota = RedisTenantQuota(
        cast(Redis, redis), requests_per_minute=10, daily_token_budget=5
    )
    other_tenant_quota.reserve("tenant-b", 5)
    with pytest.raises(TenantTokenBudgetExceeded):
        other_tenant_quota.reserve("tenant-b", 1)


def test_redis_quota_fails_closed_when_redis_is_unavailable() -> None:
    redis = FakeRedis()
    redis.fail = True
    quota = RedisTenantQuota(cast(Redis, redis), requests_per_minute=10, daily_token_budget=10)

    with pytest.raises(TenantQuotaUnavailable):
        quota.reserve("tenant-a", 1)
