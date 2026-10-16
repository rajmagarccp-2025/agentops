from typing import Any

from platform_api.governance.schemas import PolicyDecision
from platform_api.mcp.types import ToolRisk
from platform_api.security import Principal


class PolicyEngine:
    def __init__(self, version: str = "v1.0.0") -> None:
        self.version = version
        self._policy_versions: dict[str, dict[str, Any]] = {
            "v1.0.0": {"active": True, "fail_closed_mutations": True},
            "v1.1.0": {"active": True, "fail_closed_mutations": True},
        }

    def evaluate(
        self,
        *,
        principal: Principal | None = None,
        environment: str,
        action: str,
        risk: ToolRisk,
        target_tenant_id: str | None = None,
        policy_version: str | None = None,
        controls_available: bool = True,
        required_permission: str | None = None,
    ) -> PolicyDecision:
        active_version = policy_version or self.version

        # 1. Fail Closed Enforcement for Mutations when controls/services are unavailable
        is_mutation = risk in {ToolRisk.HIGH_RISK, ToolRisk.CRITICAL} or action.lower() in {
            "delete",
            "scale",
            "rollback",
            "mutate",
            "restart",
        }
        if not controls_available and is_mutation:
            reason = (
                "FAIL CLOSED: Required governance controls are unavailable "
                "for infrastructure mutation."
            )
            return PolicyDecision(
                allowed=False,
                require_human_approval=False,
                reason=reason,
                risk=risk,
            )

        # 2. RBAC & Tenant/Object Authorization Validation
        if principal:
            if target_tenant_id and principal.tenant_id != target_tenant_id:
                return PolicyDecision(
                    allowed=False,
                    require_human_approval=False,
                    reason=(
                        f"DENIED: Principal tenant '{principal.tenant_id}' does not "
                        f"match target tenant '{target_tenant_id}'."
                    ),
                    risk=risk,
                )

            if required_permission:
                alt_permission = (
                    required_permission.replace(".", ":")
                    if "." in required_permission
                    else required_permission.replace(":", ".")
                )
                has_perm = (
                    required_permission in principal.permissions
                    or alt_permission in principal.permissions
                    or "platform:admin" in principal.permissions
                    or "platform.admin" in principal.permissions
                )
                if not has_perm:
                    return PolicyDecision(
                        allowed=False,
                        require_human_approval=False,
                        reason=(
                            f"DENIED: Principal '{principal.subject}' lacks required "
                            f"permission '{required_permission}'."
                        ),
                        risk=risk,
                    )

        # 3. Policy Version Validation
        if (
            active_version not in self._policy_versions
            or not self._policy_versions[active_version]["active"]
        ):
            return PolicyDecision(
                allowed=False,
                require_human_approval=False,
                reason=f"DENIED: Policy version '{active_version}' is invalid or inactive.",
                risk=risk,
            )

        # 4. Risk Classification & Decision Matrix (DENY / APPROVAL_REQUIRED / ALLOW)
        if risk == ToolRisk.CRITICAL and environment.lower() == "production":
            return PolicyDecision(
                allowed=True,
                require_human_approval=True,
                reason=(
                    "CRITICAL production action requires explicit human approval "
                    "and dual-authorization."
                ),
                risk=risk,
            )

        if risk in {ToolRisk.HIGH_RISK, ToolRisk.CRITICAL}:
            return PolicyDecision(
                allowed=True,
                require_human_approval=True,
                reason="High-risk actions require explicit human approval.",
                risk=risk,
            )

        if environment.lower() == "production" and action.lower() in {
            "delete",
            "rollback",
            "scale",
        }:
            return PolicyDecision(
                allowed=True,
                require_human_approval=True,
                reason="Production destructive actions require human approval.",
                risk=risk,
            )

        return PolicyDecision(
            allowed=True,
            require_human_approval=False,
            reason=f"Action '{action}' permitted by policy version '{active_version}'.",
            risk=risk,
        )


policy_engine = PolicyEngine()
