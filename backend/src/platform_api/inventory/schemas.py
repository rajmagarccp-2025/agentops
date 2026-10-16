from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResourceKind(StrEnum):
    COMPUTE = "compute"
    DATABASE = "database"
    KUBERNETES = "kubernetes"
    NETWORK = "network"
    STORAGE = "storage"


class InventoryResource(BaseModel):
    resource_id: str = Field(min_length=1, max_length=255)
    provider: str = Field(min_length=1, max_length=50)
    kind: ResourceKind
    name: str = Field(min_length=1, max_length=255)
    region: str = Field(min_length=1, max_length=100)
    environment: str = Field(min_length=1, max_length=100)
    service: str | None = Field(default=None, max_length=200)
    status: str = Field(default="unknown", max_length=50)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_fresh: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyGraphNode(BaseModel):
    source: str
    target: str
    dependency_type: str = "network"
    confidence: float = 1.0


class DiscoverySummary(BaseModel):
    total_resources: int
    deduplicated_count: int
    kinds_count: dict[str, int]
    coverage_percentage: float
    freshness_seconds: float
    tenant_id: str


class InventorySnapshot(BaseModel):
    tenant_id: str
    resources: list[InventoryResource]
    accounts: list[dict[str, str]] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    dependencies: list[DependencyGraphNode] = Field(default_factory=list)
    summary: DiscoverySummary | None = None
