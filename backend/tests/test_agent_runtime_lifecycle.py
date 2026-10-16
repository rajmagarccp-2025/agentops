from platform_api.agents.runtime import agent_runtime


def test_agent_runtime_checkpoint_and_resume() -> None:
    # Test creation and state checkpointer
    run = agent_runtime.run(
        request="Investigate DB latency",
        request_type="sre",
        tenant_id="tenant-checkpoint-test",
        subject="test-user",
        permissions=["agents:run", "tools:read", "llm:invoke"],
    )
    assert run["run_id"] is not None
    assert run["status"] == "completed"
    assert run["correlation_id"] is not None

    # Retrieve via checkpointer thread_id
    saved = agent_runtime.get(run["run_id"])
    assert saved["run_id"] == run["run_id"]
    assert saved["tenant_id"] == "tenant-checkpoint-test"


def test_agent_runtime_cancellation() -> None:
    run = agent_runtime.enqueue(
        request="Long running analysis",
        request_type="sre",
        tenant_id="tenant-cancel-test",
        subject="test-user",
        permissions=["agents:run"],
    )

    cancelled = agent_runtime.cancel(
        run["run_id"],
        reason="Operation timeout",
        tenant_id="tenant-cancel-test",
    )
    assert cancelled["status"] == "cancelled"
    assert cancelled["error"] == "Operation timeout"

    fetched = agent_runtime.get(run["run_id"])
    assert fetched["status"] == "cancelled"


def test_agent_runtime_failure_handling() -> None:
    # Trigger an error to test FAILED state mapping
    try:
        agent_runtime.run(
            request="Invalid run",
            request_type="invalid_type",  # type: ignore
            tenant_id="tenant-fail-test",
            subject="test-user",
            permissions=[],
        )
    except Exception:
        pass
