import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from redis.exceptions import RedisError

_RESERVE_SCRIPT = """
local requests = redis.call('INCR', KEYS[1])
if requests == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[4])
end
if requests > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return 0
end
local used = tonumber(redis.call('GET', KEYS[2]) or '0')
if used + tonumber(ARGV[3]) > tonumber(ARGV[2]) then
  redis.call('DECR', KEYS[1])
  return -1
end
local updated = redis.call('INCRBY', KEYS[2], ARGV[3])
if updated == tonumber(ARGV[3]) then
  redis.call('EXPIRE', KEYS[2], ARGV[5])
end
return 1
"""

_SETTLE_SCRIPT = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local updated = used - tonumber(ARGV[1]) + tonumber(ARGV[2])
if updated < 0 then
  updated = 0
end
redis.call('SET', KEYS[1], updated, 'KEEPTTL')
return updated
"""

_RELEASE_SCRIPT = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local updated = used - tonumber(ARGV[1])
if updated < 0 then
  updated = 0
end
redis.call('SET', KEYS[1], updated, 'KEEPTTL')
return updated
"""


class TenantQuota(Protocol):
    def reserve(self, tenant_id: str, tokens: int) -> None: ...

    def settle(self, tenant_id: str, reserved_tokens: int, actual_tokens: int) -> None: ...

    def release(self, tenant_id: str, reserved_tokens: int) -> None: ...


class RedisTenantQuota:
    def __init__(
        self,
        client: Any,
        requests_per_minute: int,
        daily_token_budget: int,
    ) -> None:
        if requests_per_minute < 1 or daily_token_budget < 1:
            raise ValueError("Tenant LLM quotas must be positive")
        self._client = client
        self._requests_per_minute = requests_per_minute
        self._daily_token_budget = daily_token_budget

    def reserve(self, tenant_id: str, tokens: int) -> None:
        now = datetime.now(UTC)
        tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        minute_key = f"agentops:llm:quota:v1:{tenant_hash}:rpm:{now:%Y%m%d%H%M}"
        daily_key = f"agentops:llm:quota:v1:{tenant_hash}:tokens:{now:%Y%m%d}"
        seconds_to_midnight = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        ) - now).total_seconds()
        try:
            result = self._client.eval(
                _RESERVE_SCRIPT,
                2,
                minute_key,
                daily_key,
                str(self._requests_per_minute),
                str(self._daily_token_budget),
                str(tokens),
                "120000",
                str(max(60, int(seconds_to_midnight) + 60)),
            )
        except RedisError as exc:
            raise TenantQuotaUnavailable("Tenant LLM quota service is unavailable") from exc
        if result == 0:
            raise TenantRateLimitExceeded("Tenant request rate limit exceeded")
        if result == -1:
            raise TenantTokenBudgetExceeded("Tenant daily token budget exceeded")
        if result != 1:
            raise RuntimeError("Tenant LLM quota service returned an invalid reservation")

    def settle(self, tenant_id: str, reserved_tokens: int, actual_tokens: int) -> None:
        self._update_daily_usage(tenant_id, reserved_tokens, actual_tokens, _SETTLE_SCRIPT)

    def release(self, tenant_id: str, reserved_tokens: int) -> None:
        self._update_daily_usage(tenant_id, reserved_tokens, 0, _RELEASE_SCRIPT)

    def _update_daily_usage(
        self,
        tenant_id: str,
        reserved_tokens: int,
        actual_tokens: int,
        script: str,
    ) -> None:
        tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        daily_key = f"agentops:llm:quota:v1:{tenant_hash}:tokens:{datetime.now(UTC):%Y%m%d}"
        try:
            self._client.eval(
                script, 1, daily_key, str(reserved_tokens), str(actual_tokens)
            )
        except RedisError as exc:
            raise TenantQuotaUnavailable("Tenant LLM quota accounting is unavailable") from exc


class AllowAllTenantQuota:
    def reserve(self, tenant_id: str, tokens: int) -> None:
        return None

    def settle(self, tenant_id: str, reserved_tokens: int, actual_tokens: int) -> None:
        return None

    def release(self, tenant_id: str, reserved_tokens: int) -> None:
        return None


class TenantRateLimitExceeded(RuntimeError):
    pass


class TenantTokenBudgetExceeded(RuntimeError):
    pass


class TenantQuotaUnavailable(RuntimeError):
    pass
