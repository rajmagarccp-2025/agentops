"""Production background async worker for AgentOps platform.

Handles background jobs, asynchronous event processing, telemetry queue consumers,
and scheduled maintenance tasks.
"""

import asyncio
import logging
import os
import signal
import sys
import time
import uuid

from pydantic import ValidationError

from platform_api.config import get_settings
from platform_api.database import SessionLocal, init_db
from platform_api.logging_config import configure_logging
from platform_api.observability import increment
from platform_api.secrets.lifecycle import archive_old_audit_events, process_secret_lifecycle
from platform_api.workflow_pubsub import (
    PubSubWorkflowTransport,
    PulledWorkflowMessage,
    parse_dispatch_message,
)
from platform_api.workflow_queue import WorkflowJobRecord, WorkflowJobStatus, workflow_queue

logger = logging.getLogger("platform_api.worker")


class BackgroundWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        self.worker_id = f"{os.environ.get('HOSTNAME', 'worker')}:{os.getpid()}:{uuid.uuid4()}"
        self._active_jobs: set[asyncio.Task[None]] = set()
        self._last_lifecycle_run = 0.0
        self._last_archive_run = 0.0
        self._last_outbox_cleanup_run = 0.0
        self._last_heartbeat_run = 0.0
        self._last_database_poll = 0.0
        self._pubsub_transport = (
            PubSubWorkflowTransport() if self.settings.workflow_queue_backend == "pubsub" else None
        )

    async def start(self) -> None:
        self.is_running = True
        logger.info("Initializing AgentOps Background Worker Subsystem...")

        # Initialize and verify database connectivity
        try:
            init_db()
            with SessionLocal() as db:
                from sqlalchemy import text

                db.execute(text("SELECT 1"))
            logger.info("Worker database connection established and verified.")
        except Exception:
            logger.exception("Worker initial database check failed; retrying in loop")

        # Main processing loop
        iteration = 0
        while self.is_running and not self._shutdown_event.is_set():
            iteration += 1
            try:
                await self._process_tick(iteration)
            except Exception:
                logger.exception("Workflow worker tick failed")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
            except TimeoutError:
                pass

        if self._active_jobs:
            await asyncio.gather(*self._active_jobs, return_exceptions=True)
        if self._pubsub_transport is not None:
            await asyncio.to_thread(self._pubsub_transport.close)
        try:
            await asyncio.to_thread(
                workflow_queue.record_worker_heartbeat,
                worker_id=self.worker_id,
                status="stopped",
                active_jobs=0,
            )
        except Exception:
            logger.exception("Could not persist worker shutdown heartbeat")
        logger.info("AgentOps Background Worker shutdown cleanly.")

    async def _process_tick(self, iteration: int) -> None:
        if iteration % 6 == 1:  # Log heartbeat every ~60 seconds
            logger.info(
                "AgentOps background worker heartbeat [Tick: %d, Env: %s]",
                iteration,
                self.settings.app_env,
            )
        completed_jobs = {job for job in self._active_jobs if job.done()}
        for task in completed_jobs:
            if task.cancelled():
                continue
            error = task.exception()
            if error is not None:
                logger.error(
                    "Workflow worker task failed unexpectedly",
                    exc_info=(type(error), error, error.__traceback__),
                )
        self._active_jobs.difference_update(completed_jobs)
        now = time.monotonic()
        if now - self._last_heartbeat_run >= 15:
            self._last_heartbeat_run = now
            try:
                await asyncio.to_thread(
                    workflow_queue.record_worker_heartbeat,
                    worker_id=self.worker_id,
                    status="running",
                    active_jobs=len(self._active_jobs),
                )
            except Exception:
                logger.exception("Could not persist worker heartbeat")
                increment("workflow.worker.heartbeat_errors")
        available = self.settings.workflow_worker_concurrency - len(self._active_jobs)
        if self._pubsub_transport is None:
            await self._claim_database_jobs(available)
        else:
            await self._publish_outbox_messages()
            try:
                await self._pull_pubsub_messages(available)
            except Exception:
                self._last_database_poll = 0.0
                logger.exception("Pub/Sub workflow pull failed; database polling remains active")
                increment("workflow.pubsub.pull_errors")
            if time.monotonic() - self._last_database_poll >= 30:
                self._last_database_poll = time.monotonic()
                await self._claim_database_jobs(
                    self.settings.workflow_worker_concurrency - len(self._active_jobs)
                )
        if now - self._last_lifecycle_run >= self.settings.secret_expiry_scan_interval_seconds:
            self._last_lifecycle_run = now
            try:
                await asyncio.to_thread(process_secret_lifecycle)
            except Exception:
                logger.exception("Secret lifecycle scan failed")
                increment("secrets.lifecycle.scan_errors")
        archive_interval = min(
            self.settings.secret_expiry_scan_interval_seconds,
            3_600,
        )
        if now - self._last_archive_run >= archive_interval:
            self._last_archive_run = now
            try:
                await asyncio.to_thread(
                    archive_old_audit_events,
                    retention_days=self.settings.audit_archive_after_days,
                )
            except Exception:
                logger.exception("Audit archive task failed")
                increment("audit.archive.errors")
        if self._pubsub_transport is not None and now - self._last_outbox_cleanup_run >= 86_400:
            self._last_outbox_cleanup_run = now
            try:
                purged = await asyncio.to_thread(
                    workflow_queue.purge_published_outbox,
                    retention_days=self.settings.workflow_outbox_retention_days,
                )
                increment("workflow.outbox.purged", purged)
            except Exception:
                logger.exception("Workflow outbox retention cleanup failed")
                increment("workflow.outbox.cleanup_errors")

    async def _claim_database_jobs(self, available: int) -> None:
        for _ in range(max(0, available)):
            job = await asyncio.to_thread(
                workflow_queue.claim_next,
                worker_id=self.worker_id,
                lease_seconds=self.settings.workflow_job_lease_seconds,
            )
            if job is None:
                break
            task = asyncio.create_task(self._execute_job(job))
            self._active_jobs.add(task)

    async def _publish_outbox_messages(self) -> None:
        if self._pubsub_transport is None:
            return
        messages = await asyncio.to_thread(
            workflow_queue.claim_outbox_messages,
            worker_id=self.worker_id,
            limit=self.settings.workflow_pubsub_poll_batch_size,
        )
        for message in messages:
            try:
                from platform_api.workflow_pubsub import WorkflowDispatchMessage

                await asyncio.to_thread(
                    self._pubsub_transport.publish,
                    WorkflowDispatchMessage.from_outbox(message),
                )
            except Exception as exc:
                await asyncio.to_thread(
                    workflow_queue.retry_outbox_publish,
                    message.id,
                    worker_id=self.worker_id,
                    error=str(exc),
                )
                logger.warning("Pub/Sub outbox publish failed: outbox_id=%s", message.id)
            else:
                await asyncio.to_thread(
                    workflow_queue.mark_outbox_published,
                    message.id,
                    worker_id=self.worker_id,
                )

    async def _pull_pubsub_messages(self, available: int) -> None:
        if self._pubsub_transport is None or available <= 0:
            return
        messages = await asyncio.to_thread(
            self._pubsub_transport.pull,
            min(available, self.settings.workflow_pubsub_poll_batch_size),
        )
        for message in messages:
            task = asyncio.create_task(self._handle_pubsub_delivery(message))
            self._active_jobs.add(task)

    async def _handle_pubsub_delivery(self, message: PulledWorkflowMessage) -> None:
        if self._pubsub_transport is None:
            return
        try:
            dispatch = parse_dispatch_message(message.data)
        except (ValidationError, ValueError):
            increment("workflow.pubsub.poison_messages")
            await self._nack_pubsub_message(message.ack_id)
            return

        job = await asyncio.to_thread(workflow_queue.get, dispatch.job_id)
        if (
            job is None
            or job.tenant_id != dispatch.tenant_id
            or (job.idempotency_key or job.id) != dispatch.idempotency_key
        ):
            increment("workflow.pubsub.invalid_messages")
            await self._nack_pubsub_message(message.ack_id)
            return

        claimed = await asyncio.to_thread(
            workflow_queue.claim_by_id,
            dispatch.job_id,
            worker_id=self.worker_id,
        )
        if claimed is None:
            # A prior delivery or the database recovery poll already owns this job.
            await self._ack_pubsub_message(message.ack_id)
            return

        heartbeat = asyncio.create_task(self._extend_pubsub_deadline(message.ack_id))
        try:
            await self._execute_job(claimed)
            current = await asyncio.to_thread(workflow_queue.get, dispatch.job_id)
            if current is not None and current.status != WorkflowJobStatus.RUNNING:
                await self._ack_pubsub_message(message.ack_id)
            else:
                await self._nack_pubsub_message(message.ack_id)
        except Exception:
            logger.exception("Pub/Sub workflow message processing failed")
            await self._nack_pubsub_message(message.ack_id)
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass

    async def _extend_pubsub_deadline(self, ack_id: str) -> None:
        if self._pubsub_transport is None:
            return
        while True:
            await asyncio.sleep(self.settings.workflow_pubsub_ack_extension_seconds // 3)
            try:
                await asyncio.to_thread(
                    self._pubsub_transport.extend_ack_deadline,
                    ack_id,
                    self.settings.workflow_pubsub_ack_extension_seconds,
                )
            except Exception:
                increment("workflow.pubsub.ack_extension_errors")
                logger.warning("Could not extend Pub/Sub workflow acknowledgement deadline")

    async def _ack_pubsub_message(self, ack_id: str) -> None:
        if self._pubsub_transport is None:
            return
        try:
            await asyncio.to_thread(self._pubsub_transport.acknowledge, ack_id)
        except Exception:
            increment("workflow.pubsub.ack_errors")
            logger.warning("Could not acknowledge Pub/Sub workflow message")

    async def _nack_pubsub_message(self, ack_id: str) -> None:
        if self._pubsub_transport is None:
            return
        try:
            await asyncio.to_thread(self._pubsub_transport.negative_acknowledge, ack_id)
        except Exception:
            increment("workflow.pubsub.nack_errors")
            logger.warning("Could not reject Pub/Sub workflow message")

    async def _execute_job(self, job: WorkflowJobRecord) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "platform_api.workflow_job_runner",
                job.id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            communicate_task = asyncio.create_task(process.communicate())
            deadline = asyncio.get_running_loop().time() + job.timeout_seconds
            while not communicate_task.done():
                current = workflow_queue.get(job.id)
                if current is None or current.status == WorkflowJobStatus.CANCELLED:
                    process.terminate()
                    await process.wait()
                    await communicate_task
                    increment("workflow.jobs.cancelled")
                    return
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    process.kill()
                    await process.wait()
                    await communicate_task
                    logger.error("Workflow job timed out and was terminated: job_id=%s", job.id)
                    increment("workflow.jobs.timed_out")
                    workflow_queue.mark_failed(
                        job.id,
                        error=(
                            f"Job exceeded its {job.timeout_seconds}-second timeout "
                            "and was terminated"
                        ),
                        retryable=bool(job.payload.get("retry_safe", False)),
                    )
                    return
                try:
                    await asyncio.wait_for(
                        asyncio.shield(communicate_task), timeout=min(2, remaining)
                    )
                except TimeoutError:
                    continue
            stdout, stderr = communicate_task.result()

            if process.returncode:
                logger.error(
                    "Workflow job process failed: job_id=%s returncode=%s stderr=%s",
                    job.id,
                    process.returncode,
                    stderr.decode(errors="replace")[-4000:],
                )
                increment("workflow.jobs.process_errors")
                workflow_queue.mark_failed(
                    job.id,
                    error=stderr.decode(errors="replace")[-4000:] or "Workflow subprocess failed",
                    retryable=bool(job.payload.get("retry_safe", False)),
                )
            elif stdout:
                logger.debug("Workflow job completed: job_id=%s output=%s", job.id, stdout[-1000:])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Workflow subprocess could not complete: job_id=%s", job.id)
            workflow_queue.mark_failed(
                job.id,
                error=str(exc),
                retryable=bool(job.payload.get("retry_safe", False)),
            )

    def stop(self) -> None:
        logger.info("Received worker shutdown signal...")
        self.is_running = False
        self._shutdown_event.set()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    worker = BackgroundWorker()

    loop = asyncio.get_running_loop()

    # Handle termination signals
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            # Signal handling on Windows
            pass

    try:
        await worker.start()
    except (KeyboardInterrupt, SystemExit):
        worker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
