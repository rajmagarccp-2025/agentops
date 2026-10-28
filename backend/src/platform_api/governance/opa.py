from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from platform_api.config import get_settings
from platform_api.observability import increment


class OPADecision(BaseModel):
    allowed: bool
    require_human_approval: bool
    policy_version: str
    reason: str


class OPAUnavailable(RuntimeError):
    pass


class OPAPolicyClient:
    def evaluate(self, input_document: dict[str, Any]) -> OPADecision | None:
        settings = get_settings()
        endpoint = settings.opa_url
        if not endpoint:
            if settings.opa_required or settings.app_env.lower() == "production":
                increment("policy.opa.unavailable")
                raise OPAUnavailable("Required policy decision service is not configured")
            return None

        try:
            response = httpx.post(
                f"{endpoint.rstrip('/')}/v1/data/agentops/authz/decision",
                json={"input": input_document},
                timeout=settings.opa_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            decision = OPADecision.model_validate(result)
        except (httpx.HTTPError, ValueError, TypeError, ValidationError) as exc:
            increment("policy.opa.errors")
            raise OPAUnavailable("Policy decision service returned no valid decision") from exc

        if decision.policy_version != input_document.get("policy_version"):
            increment("policy.opa.stale")
            raise OPAUnavailable("Policy decision service returned a stale policy version")
        increment("policy.opa.allowed" if decision.allowed else "policy.opa.denied")
        return decision


opa_policy_client = OPAPolicyClient()


def approval_input(
    *,
    approval: dict[str, Any] | None,
    action: str,
    tool_name: str,
    tenant_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    if approval is None:
        return {
            "approved": False,
            "approval_status": "",
            "approval_tenant_id": "",
            "approval_action": "",
            "approval_tool_name": "",
            "approval_parameters": {},
            "approval_expires_at": 0,
        }
    expires_at = approval.get("expires_at")
    if isinstance(expires_at, datetime):
        expires_at = int(expires_at.timestamp() * 1_000_000_000)
    elif isinstance(expires_at, str):
        expires_at = int(datetime.fromisoformat(expires_at).timestamp() * 1_000_000_000)
    return {
        "approved": True,
        "tenant_id": tenant_id,
        "action": action,
        "tool_name": tool_name,
        "parameters": parameters,
        "approval_status": str(approval.get("status", "")).lower(),
        "approval_tenant_id": approval.get("tenant_id"),
        "approval_action": approval.get("action"),
        "approval_tool_name": approval.get("tool_name"),
        "approval_parameters": approval.get("parameters"),
        "approval_expires_at": expires_at or 0,
    }
