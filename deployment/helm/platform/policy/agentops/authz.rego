package agentops.authz

import rego.v1

policy_version := "v1.0.0"

default decision := {
	"allowed": false,
	"require_human_approval": false,
	"policy_version": "v1.0.0",
	"reason": "deny_by_default",
}

has_permission if {
	input.tool.required_permission in input.principal.permissions
}

has_permission if {
	"*" in input.principal.permissions
}

has_permission if {
	"platform:admin" in input.principal.permissions
}

tenant_matches if {
	input.tenant_id == input.principal.tenant_id
	input.target_tenant_id == input.principal.tenant_id
}

requires_approval if {
	not input.dry_run
	input.tool.risk in {"HIGH_RISK", "CRITICAL"}
}

requires_approval if {
	not input.dry_run
	input.environment == "production"
	input.action in {"delete", "rollback", "scale", "restart"}
}

approval_matches if {
	input.approved
	input.approval_status == "approved"
	input.approval_tenant_id == input.tenant_id
	input.approval_action == input.action
	input.approval_tool_name == input.tool.name
	input.approval_parameters == input.parameters
	input.approval_expires_at > time.now_ns()
}

decision := {
	"allowed": true,
	"require_human_approval": false,
	"policy_version": policy_version,
	"reason": "permitted",
} if {
	input.policy_version == policy_version
	tenant_matches
	has_permission
	not requires_approval
}

decision := {
	"allowed": true,
	"require_human_approval": true,
	"policy_version": policy_version,
	"reason": "human_approval_required",
} if {
	input.policy_version == policy_version
	tenant_matches
	has_permission
	requires_approval
	not input.approved
}

decision := {
	"allowed": true,
	"require_human_approval": false,
	"policy_version": policy_version,
	"reason": "approved",
} if {
	input.policy_version == policy_version
	tenant_matches
	has_permission
	requires_approval
	approval_matches
}
