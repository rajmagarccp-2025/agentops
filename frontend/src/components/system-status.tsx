"use client";

import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "../lib/api";

export function SystemStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal).then(setHealth).catch(() => setError(true));
    return () => controller.abort();
  }, []);

  const label = health?.status === "ok" ? "API operational" : error ? "API unavailable" : "Checking API";
  const state = health?.status === "ok" ? "healthy" : error ? "critical" : "pending";

  return (
    <span className={`system-status ${state}`}>
      <span className="pulse" aria-hidden="true" />
      {label}
    </span>
  );
}
