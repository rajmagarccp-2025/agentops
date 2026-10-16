"""Dry-run simulation and blast radius contracts."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=200)
    before_value: Any = None
    after_value: Any = None


class BlastRadius(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_resources: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    impact_score: float = Field(ge=0.0, le=10.0)


class SimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=200)
    target_resource: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    before_state: dict[str, Any] = Field(default_factory=dict)
    proposed_after_state: dict[str, Any] = Field(default_factory=dict)
    deltas: list[StateDelta] = Field(default_factory=list)
    blast_radius: BlastRadius
    expected_outcome: str = Field(min_length=1, max_length=1_000)
    reversibility: bool = True
    rollback_condition: str = Field(min_length=1, max_length=1_000)
    verification_signals: list[str] = Field(default_factory=list)
    simulated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
