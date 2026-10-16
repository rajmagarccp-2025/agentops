from platform_api.agents.runtime import agent_runtime
from platform_api.inventory.schemas import InventoryResource, ResourceKind
from platform_api.inventory.service import inventory_repository
from platform_api.security import Principal


def test_discovery_agent_unit_and_structured_output() -> None:
    principal = Principal(
        subject="discovery-user-1",
        tenant_id="tenant-disc-test",
        roles=frozenset(["user"]),
        permissions=frozenset({"agents:run", "tools:read"}),
    )

    state = agent_runtime.run(
        request="Discover all active compute and database resources and build topological map.",
        request_type="discovery",
        tenant_id=principal.tenant_id,
        subject=principal.subject,
        permissions=list(principal.permissions),
        cloud_provider="gcp",
        environment="production",
    )

    # 1. Verification of Execution & Status
    assert state["run_id"] is not None
    assert state["status"] == "completed"
    assert state["request_type"] == "discovery"
    assert state["inventory_count"] >= 2

    # 2. Structured Findings Categories (OBSERVED / INFERRED / RECOMMENDED)
    structured = state.get("structured_findings", [])
    assert len(structured) >= 3
    categories = {sf["category"] for sf in structured}
    assert "OBSERVED" in categories
    assert "INFERRED" in categories
    assert "RECOMMENDED" in categories

    # 3. Evidence & Dependency Graph Payload Verification
    evidence = state.get("evidence", [])
    assert len(evidence) > 0
    snapshot_data = evidence[0]
    assert "resources" in snapshot_data
    assert "dependencies" in snapshot_data
    assert "summary" in snapshot_data
    assert snapshot_data["summary"]["coverage_percentage"] == 100.0


def test_discovery_agent_tenant_isolation() -> None:
    tenant_a = "tenant-disc-alpha"
    tenant_b = "tenant-disc-beta"

    principal_a = Principal(
        "user-a", tenant_a, frozenset(["user"]), frozenset({"agents:run", "tools:read"})
    )
    principal_b = Principal(
        "user-b", tenant_b, frozenset(["user"]), frozenset({"agents:run", "tools:read"})
    )

    # Pre-seed distinct resources in repository for Tenant A
    res_a = InventoryResource(
        resource_id="res-alpha-001",
        provider="aws",
        kind=ResourceKind.COMPUTE,
        name="alpha-server",
        region="us-east-1",
        environment="production",
    )
    inventory_repository.replace_for_tenant(tenant_a, [res_a])

    # Run Discovery for Tenant B
    agent_runtime.run(
        request="Discover tenant beta inventory",
        request_type="discovery",
        tenant_id=principal_b.tenant_id,
        subject=principal_b.subject,
        permissions=list(principal_b.permissions),
    )

    # Verify Tenant B inventory listing contains zero Tenant A resources
    tenant_b_resources = inventory_repository.list_for_tenant(tenant_b)
    tenant_b_ids = [r.resource_id for r in tenant_b_resources]
    assert "res-alpha-001" not in tenant_b_ids

    # Verify Tenant A inventory still maintains isolated resources
    tenant_a_resources = inventory_repository.list_for_tenant(tenant_a)
    assert len(tenant_a_resources) == 1
    assert tenant_a_resources[0].resource_id == "res-alpha-001"
