from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from platform_api.config import get_settings
from platform_api.workflow_queue import WorkflowOutboxMessage


class WorkflowDispatchMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    message_id: str = Field(min_length=1, max_length=36)
    job_id: str = Field(min_length=1, max_length=36)
    tenant_id: str = Field(min_length=1, max_length=36)
    correlation_id: str = Field(min_length=1, max_length=36)
    idempotency_key: str = Field(min_length=1, max_length=255)

    @classmethod
    def from_outbox(cls, message: WorkflowOutboxMessage) -> WorkflowDispatchMessage:
        return cls(
            message_id=message.id,
            job_id=message.job_id,
            tenant_id=message.tenant_id,
            correlation_id=message.correlation_id,
            idempotency_key=message.idempotency_key,
        )


@dataclass(frozen=True)
class PulledWorkflowMessage:
    ack_id: str
    data: bytes
    pubsub_message_id: str


class PubSubWorkflowTransport:
    """GCP Pub/Sub transport carrying identifiers only; PostgreSQL remains authoritative."""

    def __init__(
        self,
        publisher_client: Any | None = None,
        subscriber_client: Any | None = None,
        *,
        project_id: str | None = None,
        topic_id: str | None = None,
        subscription_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self.project_id = project_id or settings.workflow_pubsub_project_id
        self.topic_id = topic_id or settings.workflow_pubsub_topic_id
        self.subscription_id = subscription_id or settings.workflow_pubsub_subscription_id
        if not self.project_id or not self.topic_id or not self.subscription_id:
            raise ValueError("Pub/Sub project, topic, and subscription must be configured")

        if publisher_client is None or subscriber_client is None:
            pubsub_v1 = import_module("google.cloud.pubsub_v1")

            publisher_client = publisher_client or pubsub_v1.PublisherClient()
            subscriber_client = subscriber_client or pubsub_v1.SubscriberClient()

        self._publisher = publisher_client
        self._subscriber = subscriber_client
        self.topic_path = self._publisher.topic_path(self.project_id, self.topic_id)
        self.subscription_path = self._subscriber.subscription_path(
            self.project_id, self.subscription_id
        )

    def publish(self, message: WorkflowDispatchMessage) -> None:
        future = self._publisher.publish(
            self.topic_path,
            message.model_dump_json().encode("utf-8"),
        )
        future.result(timeout=15)

    def pull(self, max_messages: int, timeout_seconds: float = 1.0) -> list[PulledWorkflowMessage]:
        response = self._subscriber.pull(
            request={
                "subscription": self.subscription_path,
                "max_messages": max_messages,
            },
            timeout=timeout_seconds,
        )
        return [
            PulledWorkflowMessage(
                ack_id=received.ack_id,
                data=bytes(received.message.data),
                pubsub_message_id=received.message.message_id,
            )
            for received in response.received_messages
        ]

    def acknowledge(self, ack_id: str) -> None:
        self._subscriber.acknowledge(
            request={"subscription": self.subscription_path, "ack_ids": [ack_id]}
        )

    def negative_acknowledge(self, ack_id: str) -> None:
        self._subscriber.modify_ack_deadline(
            request={
                "subscription": self.subscription_path,
                "ack_ids": [ack_id],
                "ack_deadline_seconds": 0,
            }
        )

    def extend_ack_deadline(self, ack_id: str, seconds: int) -> None:
        self._subscriber.modify_ack_deadline(
            request={
                "subscription": self.subscription_path,
                "ack_ids": [ack_id],
                "ack_deadline_seconds": seconds,
            }
        )

    def close(self) -> None:
        self._publisher.stop()
        self._subscriber.close()


def parse_dispatch_message(data: bytes) -> WorkflowDispatchMessage:
    return WorkflowDispatchMessage.model_validate_json(data)
