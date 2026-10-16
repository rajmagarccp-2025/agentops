"use client";

import { useEffect, useState } from "react";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import {
  fetchAgentRuns,
  fetchLLMTelemetry,
  fetchObservabilityMetrics,
  type AgentRunListItem,
  type LLMTelemetry,
  type ObservabilityMetrics,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

function formatCount(value: number | undefined): string {
  return new Intl.NumberFormat().format(value ?? 0);
}

export default function ObservabilityPage() {
  const { permissions, activeProject, activeEnvironment, isContextComplete } = useWorkspace();
  const canReadMetrics = permissions.hasPermission("observability:read");
  const canReadTelemetry = permissions.hasPermission("llm:read");
  const canReadAgentRuns = permissions.hasPermission("agents:read");
  const [metrics, setMetrics] = useState<ObservabilityMetrics | null>(null);
  const [telemetry, setTelemetry] = useState<LLMTelemetry[] | null>(null);
  const [runs, setRuns] = useState<AgentRunListItem[] | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!isContextComplete) return;
    const controller = new AbortController();
    setMetrics(null);
    setTelemetry(null);
    setRuns(null);
    setErrors({});

    if (canReadMetrics) {
      void fetchObservabilityMetrics(controller.signal)
        .then(setMetrics)
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setErrors((current) => ({ ...current, metrics: err instanceof Error ? err.message : "Unable to load metrics." }));
          }
        });
    }
    if (canReadTelemetry) {
      void fetchLLMTelemetry(controller.signal)
        .then(setTelemetry)
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setErrors((current) => ({ ...current, telemetry: err instanceof Error ? err.message : "Unable to load LLM telemetry." }));
          }
        });
    }
    if (canReadAgentRuns) {
      void fetchAgentRuns(controller.signal)
        .then(setRuns)
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setErrors((current) => ({ ...current, runs: err instanceof Error ? err.message : "Unable to load agent runs." }));
          }
        });
    }
    return () => controller.abort();
  }, [
    activeEnvironment?.id,
    activeProject?.id,
    canReadAgentRuns,
    canReadMetrics,
    canReadTelemetry,
    isContextComplete,
  ]);

  const currentRuns = runs?.filter((run) =>
    run.workspace_project_id === activeProject?.id
    && run.workspace_environment_id === activeEnvironment?.id
  ) ?? [];
  const llmTokens = telemetry?.reduce((total, item) => total + item.input_tokens + item.output_tokens, 0) ?? 0;
  const llmCost = telemetry?.reduce((total, item) => total + item.estimated_cost_usd, 0) ?? 0;
  const averageLatency = telemetry?.length
    ? telemetry.reduce((total, item) => total + item.latency_ms, 0) / telemetry.length
    : 0;
  const processMetrics = metrics?.metrics;

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">Operations <strong>/ Observability</strong></span>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Observability" permission="observability:read">
            <GlobalContextSelector />
            <section className="page-heading">
              <div>
                <span className="kicker">Operational signals</span>
                <h1>Observability</h1>
                <p className="lede">{activeProject?.name} / {activeEnvironment?.name}. Signal scope is shown on each panel.</p>
              </div>
            </section>

            <section className="dashboard-grid">
              <article className="panel panel-wide" id="metrics">
                <div className="panel-header"><h2>Platform metrics</h2><span className="panel-link">Process-wide cumulative counters</span></div>
                {!canReadMetrics && <p className="empty-state">Your role does not include observability metrics access.</p>}
                {errors.metrics && <p className="error-panel" role="alert">{errors.metrics}</p>}
                {canReadMetrics && !processMetrics && !errors.metrics && <p className="data-note" role="status">Loading process metrics…</p>}
                {processMetrics && (
                  <>
                    <div className="metric-grid">
                      {[
                        ["HTTP requests", processMetrics.http_requests_total],
                        ["HTTP 5xx responses", processMetrics.http_5xx_responses_total],
                        ["LLM requests", processMetrics.llm_requests_total],
                        ["LLM tokens", (processMetrics.llm_prompt_tokens_total ?? 0) + (processMetrics.llm_completion_tokens_total ?? 0)],
                        ["Tool executions", processMetrics.tool_executions_total],
                        ["Workflow executions", processMetrics.workflow_executions_total],
                      ].map(([label, value]) => (
                        <div className="metric-card" key={label}>
                          <span>{label}</span><strong>{formatCount(Number(value))}</strong>
                        </div>
                      ))}
                    </div>
                    <p className="data-note">These counters cover this API process since startup; they are not environment-specific or durable.</p>
                  </>
                )}
              </article>

              <article className="panel panel-wide" id="llm-usage">
                <div className="panel-header"><h2>LLM usage</h2><span className="panel-link">Tenant-wide in-memory telemetry</span></div>
                {!canReadTelemetry && <p className="empty-state">Your role does not include LLM telemetry access.</p>}
                {errors.telemetry && <p className="error-panel" role="alert">{errors.telemetry}</p>}
                {canReadTelemetry && !telemetry && !errors.telemetry && <p className="data-note" role="status">Loading LLM telemetry…</p>}
                {telemetry && (
                  <>
                    <div className="metric-grid">
                      <div className="metric-card"><span>Recorded requests</span><strong>{formatCount(telemetry.length)}</strong></div>
                      <div className="metric-card"><span>Recorded tokens</span><strong>{formatCount(llmTokens)}</strong></div>
                      <div className="metric-card"><span>Estimated cost</span><strong>${llmCost.toFixed(4)}</strong></div>
                      <div className="metric-card"><span>Mean latency</span><strong>{averageLatency.toFixed(0)} ms</strong></div>
                    </div>
                    {telemetry.length === 0 && <p className="empty-state">No LLM requests have been recorded in this process.</p>}
                    {telemetry.slice(-8).reverse().map((item) => (
                      <div className="change-row" key={item.request_id}>
                        <div><strong>{item.model}</strong><span>{item.provider} · {item.task} · {item.input_tokens + item.output_tokens} tokens</span></div>
                        <small>{item.latency_ms.toFixed(0)} ms · ${item.estimated_cost_usd.toFixed(4)}</small>
                      </div>
                    ))}
                    <p className="data-note">Telemetry is tenant-filtered by the API but is not persisted across process restarts and has no environment timestamp/filter.</p>
                  </>
                )}
              </article>

              <article className="panel panel-wide" id="agent-runs">
                <div className="panel-header"><h2>Agent runs</h2><span className="panel-link">Selected project/environment · in-memory</span></div>
                {!canReadAgentRuns && <p className="empty-state">Your role does not include agent run access.</p>}
                {errors.runs && <p className="error-panel" role="alert">{errors.runs}</p>}
                {canReadAgentRuns && !runs && !errors.runs && <p className="data-note" role="status">Loading agent runs…</p>}
                {runs && currentRuns.map((run) => (
                  <div className="change-row" key={run.run_id}>
                    <div><strong>{run.request_type} · {run.status}</strong><span>{run.target_resource ?? "No target resource"}{run.error ? ` · ${run.error}` : ""}</span></div>
                    <small>{new Date(run.updated_at).toLocaleString()}</small>
                  </div>
                ))}
                {runs && currentRuns.length === 0 && <p className="empty-state">No recent agent runs exist for this selected project and environment.</p>}
                <p className="data-note">Run history comes from the active runtime checkpoint store and is lost when the backend restarts.</p>
              </article>

              <article className="panel panel-wide" id="logs-traces">
                <div className="panel-header"><h2>Logs and traces</h2><span className="panel-link">Not queryable in this deployment</span></div>
                <p className="empty-state">
                  The service can export spans through OTLP when configured, but this application has no connected trace/log query backend.
                  Configure an authenticated telemetry backend and query API before enabling these views.
                </p>
              </article>
            </section>
            {processMetrics && <p className="data-note">Counter snapshot captured {new Date(metrics?.snapshot_at ?? "").toLocaleString()}.</p>}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
