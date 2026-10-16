"use client";

import { useEffect, useState } from "react";

import {
  fetchFinOpsSummary,
  fetchInventory,
  fetchLLMTelemetry,
  type FinOpsSummary,
  type InventoryResource,
  type LLMTelemetry,
} from "../lib/api";

export function OverviewData() {
  const [data, setData] = useState<{
    finops: FinOpsSummary;
    inventory: InventoryResource[];
    llm: LLMTelemetry[];
  } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchFinOpsSummary(controller.signal),
      fetchInventory(controller.signal),
      fetchLLMTelemetry(controller.signal),
    ])
      .then(([finops, inventory, llm]) => setData({ finops, inventory, llm }))
      .catch(() => setError(true));
    return () => controller.abort();
  }, []);

  if (error) {
    return <p className="data-note warning">Live overview data is unavailable. Showing the operational shell.</p>;
  }
  if (!data) {
    return <p className="data-note">Loading live operational signals...</p>;
  }

  const latestTelemetry = data.llm.at(-1);
  const recommendationCount = data.finops.recommendations.length;
  return (
    <div className="live-signals" aria-label="Live operational signals">
      <span>{data.inventory.length} inventory resources</span>
      <span>${data.finops.total_cost_usd.toLocaleString()} tracked spend</span>
      <span>{recommendationCount} FinOps recommendations</span>
      <span>{latestTelemetry ? `${Math.round(latestTelemetry.latency_ms)}ms latest model latency` : "No LLM calls yet"}</span>
    </div>
  );
}
