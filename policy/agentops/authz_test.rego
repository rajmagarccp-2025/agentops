package agentops.authz

import rego.v1

base_input := {
	"principal": {
		"tenant_id": "tenant-a",
		"permissions": ["tools:execute"],
	},
	"tenant_id": "tenant-a",
	"target_tenant_id": "tenant-a",
	"action": "scale",
	"environment": "staging",
	"dry_run": false,
	"approved": false,
	"policy_version": "v1.0.0",
	"tool": {
		"name": "kubernetes.scale_deployment",
		"risk": "HIGH_RISK",
		"required_permission": "tools:execute",
	},
	"parameters": {"namespace": "staging", "deployment": "api", "replicas": 4},
}

test_high_risk_requires_approval if {
	result := decision with input as base_input
	result.allowed
	result.require_human_approval
}

test_low_risk_read_allowed if {
	test_input := object.union(base_input, {
		"action": "read",
		"tool": {
			"name": "kubernetes.get_deployment",
			"risk": "LOW_RISK",
			"required_permission": "tools:execute",
		},
	})
	result := decision with input as test_input
	result.allowed
	not result.require_human_approval
}

test_tenant_mismatch_denied if {
	test_input := object.union(base_input, {"target_tenant_id": "tenant-b"})
	result := decision with input as test_input
	not result.allowed
}

test_missing_permission_denied if {
	test_input := object.union(base_input, {"principal": {"tenant_id": "tenant-a", "permissions": []}})
	result := decision with input as test_input
	not result.allowed
}

test_stale_policy_denied if {
	test_input := object.union(base_input, {"policy_version": "v0.9.0"})
	result := decision with input as test_input
	not result.allowed
}

test_expired_approval_denied if {
	test_input := object.union(base_input, {
		"approved": true,
		"approval_status": "approved",
		"approval_tenant_id": "tenant-a",
		"approval_action": "scale",
		"approval_tool_name": "kubernetes.scale_deployment",
		"approval_parameters": base_input.parameters,
		"approval_expires_at": 1,
	})
	result := decision with input as test_input
	not result.allowed
}

test_approval_parameter_mismatch_denied if {
	test_input := object.union(base_input, {
		"approved": true,
		"approval_status": "approved",
		"approval_tenant_id": "tenant-a",
		"approval_action": "scale",
		"approval_tool_name": "kubernetes.scale_deployment",
		"approval_parameters": {"namespace": "staging", "deployment": "api", "replicas": 99},
		"approval_expires_at": time.now_ns() + 60000000000,
	})
	result := decision with input as test_input
	not result.allowed
}

test_approved_exact_action_allowed if {
	test_input := object.union(base_input, {
		"approved": true,
		"approval_status": "approved",
		"approval_tenant_id": "tenant-a",
		"approval_action": "scale",
		"approval_tool_name": "kubernetes.scale_deployment",
		"approval_parameters": base_input.parameters,
		"approval_expires_at": time.now_ns() + 60000000000,
	})
	result := decision with input as test_input
	result.allowed
	not result.require_human_approval
}

test_production_critical_requires_approval if {
	test_input := object.union(base_input, {
		"environment": "production",
		"tool": {
			"name": "kubernetes.scale_deployment",
			"risk": "CRITICAL",
			"required_permission": "tools:execute",
		},
	})
	result := decision with input as test_input
	result.allowed
	result.require_human_approval
}
