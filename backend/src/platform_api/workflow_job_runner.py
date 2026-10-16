from __future__ import annotations

import logging
import sys
from typing import Any

from platform_api.agents.service import agent_runtime
from platform_api.config import get_settings
from platform_api.logging_config import configure_logging
from platform_api.workflow_queue import WorkflowJobStatus, workflow_queue

logger = logging.getLogger("platform_api.workflow_job_runner")


def run_job(job_id: str) -> int:
    job = workflow_queue.get(job_id)
    if job is None:
        logger.error("Workflow job does not exist: job_id=%s", job_id)
        return 2
    if job.status != WorkflowJobStatus.RUNNING:
        logger.error("Workflow job is not claimed: job_id=%s status=%s", job_id, job.status)
        return 2
    if job.job_type != "agent_run":
        workflow_queue.mark_failed(
            job_id, error=f"Unsupported workflow job type: {job.job_type}", retryable=False
        )
        return 2

    payload: dict[str, Any] = dict(job.payload)
    retry_safe = bool(payload.pop("retry_safe", False))
    try:
        state = agent_runtime.run(**payload)
        if state.get("status") == "failed":
            workflow_queue.mark_failed(
                job_id,
                error=str(state.get("error", "Workflow execution failed")),
                retryable=retry_safe,
            )
            return 1
        workflow_queue.mark_succeeded(
            job_id,
            result={"run_id": state["run_id"], "status": state.get("status", "completed")},
        )
        return 0
    except Exception as exc:
        logger.exception("Workflow job raised an unhandled exception: job_id=%s", job_id)
        workflow_queue.mark_failed(job_id, error=str(exc), retryable=retry_safe)
        return 1


def main() -> None:
    configure_logging(get_settings().log_level)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m platform_api.workflow_job_runner JOB_ID")
    raise SystemExit(run_job(sys.argv[1]))


if __name__ == "__main__":
    main()
