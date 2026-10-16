"use client";

import { useCallback, useEffect, useState } from "react";
import { DemoTopBanner } from "./demo-top-banner";
import { Navigation } from "./navigation";
import { SystemStatus } from "./system-status";
import { ContextGuard } from "./context-guard";
import { GlobalContextSelector } from "./global-context-selector";
import {
  fetchAgentRun,
  fetchAgentRuns,
  runAgent,
  type AgentRunListItem,
  type AgentRunRequest,
  type AgentRunResponse,
} from "../lib/api";
import { useWorkspace } from "../state/workspace-context";

const workflows: Array<{ id: AgentRunRequest["request_type"]; label: string; description: string }> = [
  { id: "sre", label: "Kubernetes SRE Agent", description: "Investigate pod health, memory saturation, and autonomic SRE mitigations." },
  { id: "finops", label: "FinOps Optimization Agent", description: "Rightsize idle resources, analyze cost anomalies, and optimize cloud spend." },
  { id: "llmops", label: "LLMOps Monitoring Agent", description: "Monitor model performance, prompt regressions, token usage, and gateway fallbacks." },
  { id: "security", label: "Security Guardrail Agent", description: "Audit identity policies, zero-trust rules, and block unauthorized executions." },
  { id: "change", label: "Infra Drift Detection Agent", description: "Detect unmanaged terraform drift, correlate config changes, and reconcile state." },
  { id: "governance", label: "Governance & Compliance Agent", description: "Audit SOC2/PCI-DSS controls, RBAC integrity, and continuous policy guardrails." },
  { id: "remediation", label: "Auto-Remediation Agent", description: "Execute allowlisted self-healing playbooks with mandatory approval gates." },
  { id: "discovery", label: "Infrastructure Discovery Agent", description: "Collect and normalize inventory across Kubernetes clusters and multi-cloud." },
];

export function AgentsExperience({ initialTab = "overview" }: { initialTab?: "overview" | "runs" | "configuration" }) {
  const { activeOrg, activeProject, activeEnvironment, effectiveRole, permissions } = useWorkspace();
  const [requestType, setRequestType] = useState<AgentRunRequest["request_type"]>("sre");
  const [provider, setProvider] = useState("gcp");
  const [targetResource, setTargetResource] = useState("");
  const [request, setRequest] = useState("");
  const [result, setResult] = useState<AgentRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [tab, setTab] = useState<"overview" | "runs" | "configuration">(initialTab);
  const [runs, setRuns] = useState<AgentRunListItem[]>([]);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [selectedRunLoading, setSelectedRunLoading] = useState(false);

  const selectedWorkflow = workflows.find((workflow) => workflow.id === requestType);
  const canViewAgents = permissions.hasPermission("agents:read");
  const canRunAgents = permissions.hasPermission("agents:run");
  const activeOrganizationId = activeOrg?.id;

  const loadRuns = useCallback(async (signal?: AbortSignal) => {
    setRunsLoading(true);
    setRunsError(null);
    try {
      setRuns(await fetchAgentRuns(signal));
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setRunsError(err instanceof Error ? err.message : "Unable to load recent agent runs.");
      }
    } finally {
      if (!signal?.aborted) setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    const requestedWorkflow = new URLSearchParams(window.location.search).get("workflow");
    const workflow = workflows.find((item) => item.id === requestedWorkflow);
    if (workflow) setRequestType(workflow.id);
  }, []);

  useEffect(() => {
    if (!canViewAgents || !activeOrganizationId) return;
    const controller = new AbortController();
    setResult(null);
    setError(null);
    setRuns([]);
    void loadRuns(controller.signal);
    return () => controller.abort();
  }, [activeOrganizationId, activeProject?.id, activeEnvironment?.id, canViewAgents, loadRuns]);

  useEffect(() => {
    if (!result || !["pending", "running", "retrying"].includes(result.status)) return;
    let cancelled = false;
    let timeout: number | undefined;

    const poll = async () => {
      try {
        const updated = await fetchAgentRun(result.run_id);
        if (cancelled) return;
        setResult(updated);
        if (["completed", "failed", "cancelled", "paused", "dead_letter"].includes(updated.status)) {
          if (updated.status === "failed" || updated.status === "dead_letter") {
            setError(updated.error || "The workflow did not complete.");
          }
          void loadRuns();
          return;
        }
        timeout = window.setTimeout(() => void poll(), 1500);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to refresh workflow status.");
        }
      }
    };

    timeout = window.setTimeout(() => void poll(), 1000);
    return () => {
      cancelled = true;
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [result?.run_id, result?.status, loadRuns]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canRunAgents) {
      setError("Your role does not have permission to run agents.");
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await runAgent({
        request: request.trim(),
        request_type: requestType,
        cloud_provider: provider,
        environment: activeEnvironment?.name ?? "unspecified",
        target_resource: targetResource.trim(),
        project_id: activeProject?.id,
      });
      setResult(response);
      if (response.status === "failed") {
        setError(response.error || "The workflow did not complete.");
      }
      void loadRuns();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to start this agent workflow.");
    } finally {
      setRunning(false);
    }
  }

  async function openRun(run: AgentRunListItem) {
    setSelectedRunLoading(true);
    setError(null);
    try {
      setResult(await fetchAgentRun(run.run_id));
      setRequestType(run.request_type);
      setTab("overview");
    } catch (err: unknown) {
      setRunsError(err instanceof Error ? err.message : "Unable to load this agent run.");
    } finally {
      setSelectedRunLoading(false);
    }
  }

  const agentCardData = [
    {
      id: "sre",
      name: "Kubernetes SRE Agent",
      badge: "Autonomic SRE",
      description: "Investigated checkout-api pod memory saturation (OOMKilled mitigation)",
      runsExecuted: 342,
      successRate: "99.4%",
    },
    {
      id: "finops",
      name: "FinOps Optimization Agent",
      badge: "Cost Optimization",
      description: "Rightsized idle RDS instance r6g.2xlarge → r6g.xlarge (Saved $1,240/mo)",
      runsExecuted: 188,
      successRate: "98.9%",
    },
    {
      id: "llmops",
      name: "LLMOps Monitoring Agent",
      badge: "AI Observability",
      description: "Rerouted degraded GPT-4o traffic to Gemini 1.5 Pro fallback (Latency improved by 140ms)",
      runsExecuted: 512,
      successRate: "100%",
    },
    {
      id: "security",
      name: "Security Guardrail Agent",
      badge: "Zero-Trust Security",
      description: "Blocked unauthorized POST /ai/query invocation by READ role user",
      runsExecuted: 94,
      successRate: "100%",
    },
    {
      id: "change",
      name: "Incident Response Agent",
      badge: "Incident Mitigation",
      description: "Correlated deployment commit v2.18.4 with payment-service P1 latency spike",
      runsExecuted: 76,
      successRate: "97.3%",
    },
    {
      id: "governance",
      name: "Infra Drift Detection Agent",
      badge: "Infrastructure Drift",
      description: "Detected and synced unmanaged AWS security group modifications",
      runsExecuted: 120,
      successRate: "100%",
    },
  ];

  return (
    <div className="shell" style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <DemoTopBanner />
      <div style={{ display: "flex", flex: 1, minWidth: 0 }}>
        <Navigation />
        <div className="main" style={{ flex: 1, minWidth: 0, background: "#060b14" }}>
          <header className="topbar" style={{ display: "none" }}>
            <div className="topbar-context">
              <span className="breadcrumb">
                {activeOrg?.name || "Organization"} <strong>/ {activeProject?.name || "Project"} / {activeEnvironment?.name || "Environment"} / Agents</strong>
              </span>
            </div>
            <div className="topbar-actions"><SystemStatus /></div>
          </header>
          <main className="main-content" style={{ padding: "32px 40px", maxWidth: "1600px" }}>
            <ContextGuard featureName="Agent workflows">
              <GlobalContextSelector />

              <section style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "28px", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", margin: "0 0 6px" }}>
                    Autonomous AI Agents
                  </h1>
                  <p style={{ color: "#94a3b8", fontSize: "14px", margin: 0 }}>
                    Self-healing, multi-cloud SRE, FinOps, and LLMOps execution agents for {activeEnvironment?.name || "Production"}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setRequestType("sre");
                    setTab("overview");
                  }}
                  style={{
                    background: "#10b981",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "8px",
                    padding: "10px 18px",
                    fontSize: "13px",
                    fontWeight: "700",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                  }}
                >
                  + Create Agent (Simulated)
                </button>
              </section>

              {/* Horizontal Agent Cards matching Image 2 & 3 */}
              <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "32px" }}>
                {agentCardData.map((agent) => (
                  <div
                    key={agent.id}
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "18px 24px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "16px",
                      transition: "border-color 0.15s ease",
                    }}
                  >
                    <div style={{ flex: "1 1 400px", minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                          {agent.name}
                        </span>
                        <span
                          style={{
                            background: "rgba(16, 185, 129, 0.12)",
                            border: "1px solid rgba(16, 185, 129, 0.35)",
                            borderRadius: "6px",
                            padding: "3px 8px",
                            fontSize: "11px",
                            fontFamily: "'DM Mono', monospace",
                            color: "#34d399",
                            fontWeight: "600",
                          }}
                        >
                          {agent.badge}
                        </span>
                      </div>
                      <div style={{ fontSize: "13px", color: "#94a3b8", marginTop: "6px" }}>
                        {agent.description}
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "32px", flexWrap: "wrap" }}>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#64748b", textTransform: "uppercase" }}>
                          Runs Executed
                        </div>
                        <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff", marginTop: "2px" }}>
                          {agent.runsExecuted}
                        </div>
                      </div>

                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#64748b", textTransform: "uppercase" }}>
                          Success Rate
                        </div>
                        <div style={{ fontSize: "18px", fontWeight: "800", color: "#34d399", marginTop: "2px" }}>
                          {agent.successRate}
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          const wf = workflows.find((w) => w.id === agent.id);
                          if (wf) setRequestType(wf.id);
                          setTargetResource("checkout-api");
                          setRequest(`Investigate ${agent.name} telemetry and run health verification.`);
                          // Scroll to execution form if needed
                          const formEl = document.getElementById("execution-dock");
                          if (formEl) formEl.scrollIntoView({ behavior: "smooth" });
                        }}
                        style={{
                          background: "#172338",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          color: "#ffffff",
                          borderRadius: "8px",
                          padding: "9px 16px",
                          fontSize: "13px",
                          fontWeight: "600",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          transition: "all 0.15s ease",
                        }}
                      >
                        Run Execution →
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Execution Dock / Detailed Workspace */}
              <div id="execution-dock" style={{ marginTop: "24px" }}>
                <section className="dashboard-grid agent-grid">
                  <form className="panel agent-form" onSubmit={submit}>
                    <div className="panel-header"><h2>{selectedWorkflow?.label || "Run workflow"}</h2></div>
                    {!canRunAgents ? (
                      <p className="permission-note" role="status">
                        Your role can review agent activity but cannot start runs. Ask an organization administrator for agent-run access.
                      </p>
                    ) : (
                      <>
                    <label className="field">
                      <span>Operational question</span>
                      <textarea
                        value={request}
                        onChange={(event) => setRequest(event.target.value)}
                        required
                        maxLength={20_000}
                        rows={5}
                        placeholder={`What should the ${selectedWorkflow?.label.toLowerCase() || "workflow"} investigate?`}
                      />
                    </label>
                    <div className="field-row">
                      <label className="field">
                        <span>Provider context</span>
                        <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                          <option value="aws">AWS</option>
                          <option value="azure">Azure</option>
                          <option value="gcp">Google Cloud</option>
                          <option value="kubernetes">Kubernetes</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Target service or resource</span>
                        <input
                          value={targetResource}
                          onChange={(event) => setTargetResource(event.target.value)}
                          required
                          maxLength={200}
                          placeholder="e.g. checkout-api"
                        />
                      </label>
                    </div>
                    <p className="data-note">
                      Scope: {activeProject?.name} / {activeEnvironment?.name}. Provider integrations depend on the configured MCP adapters.
                    </p>
                    <button className="primary-button" type="submit" disabled={running}>
                      {running ? "Running workflow…" : "Run workflow"}
                    </button>
                    </>
                    )}
                  </form>

                  <section className="panel agent-result" aria-live="polite">
                <div className="panel-header"><h2>Run result</h2></div>
                {!result && !error && (
                  <p className="empty-state">Workflow findings, evidence, and governance status will appear here after a run.</p>
                )}
                {error && <p className="data-note warning" role="alert">{error}</p>}
                {result && (
                  <>
                    <dl className="run-summary">
                      <div><dt>Status</dt><dd>{result.status}</dd></div>
                      <div><dt>Run ID</dt><dd><code>{result.run_id}</code></dd></div>
                      {result.confidence !== null && <div><dt>Confidence</dt><dd>{Math.round(result.confidence * 100)}%</dd></div>}
                      {result.approval_required && <div><dt>Governance</dt><dd>Approval required</dd></div>}
                    </dl>
                    {result.approval_id && <p>Approval request: <code>{result.approval_id}</code></p>}
                    {result.recommendation && <div className="recommendation-callout"><strong>Recommendation</strong><p>{result.recommendation}</p></div>}
                    {result.findings.length > 0 && (
                      <div className="result-list">
                        <h3>Findings</h3>
                        <ul>{result.findings.map((finding, index) => <li key={`${index}-${finding}`}>{finding}</li>)}</ul>
                      </div>
                    )}
                    {result.missing_evidence.length > 0 && (
                      <div className="result-list">
                        <h3>Evidence gaps</h3>
                        <ul>{result.missing_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                    )}
                    {result.steps.length > 0 && (
                      <div className="result-list">
                        <h3>Workflow steps</h3>
                        <ul>{result.steps.map((step, index) => <li key={index}>{String(step.agent ?? step.node ?? "Step")}: {String(step.status ?? "complete")}</li>)}</ul>
                      </div>
                    )}
                    {result.findings.length === 0 && !result.recommendation && (
                      <p className="empty-state">The workflow returned no findings or recommendation.</p>
                    )}
                  </>
                )}
                  </section>
                </section>
              </div>

              <section className="panel" id="agent-panel-runs" role="tabpanel" aria-labelledby="agent-tab-runs" hidden={tab !== "runs"}>
                <div className="panel-header">
                  <div><h2>Recent runs</h2><p className="data-note">Run history is retained by the current runtime process and may not survive a backend restart.</p></div>
                  <button type="button" className="btn btn-secondary" onClick={() => void loadRuns()} disabled={runsLoading}>
                    {runsLoading ? "Refreshing…" : "Refresh"}
                  </button>
                </div>
                {runsError && <div className="error-panel" role="alert"><p>{runsError}</p></div>}
                {runsLoading && <p className="data-note" role="status">Loading recent runs…</p>}
                {!runsLoading && !runsError && runs.length === 0 && (
                  <p className="empty-state">No agent runs are available in this runtime for the selected project and environment.</p>
                )}
                {runs.map((run) => (
                  <button
                    type="button"
                    className="agent-run-row"
                    key={run.run_id}
                    onClick={() => void openRun(run)}
                    disabled={selectedRunLoading}
                  >
                    <span className={`run-status run-status-${run.status.toLowerCase()}`}>{run.status}</span>
                    <span className="agent-run-copy">
                      <strong>{workflows.find((workflow) => workflow.id === run.request_type)?.label || run.request_type}</strong>
                      <small>{run.target_resource || "No target"} · {run.environment || "Environment unavailable"} · {new Date(run.updated_at).toLocaleString()}</small>
                      {run.error && <small className="warning">{run.error}</small>}
                    </span>
                    <code>{run.run_id.slice(0, 8)}</code>
                  </button>
                ))}
              </section>

              <section className="panel" id="agent-panel-configuration" role="tabpanel" aria-labelledby="agent-tab-configuration" hidden={tab !== "configuration"}>
                <div className="panel-header"><h2>Run configuration</h2></div>
                <p>Provider context and target resource are supplied for each execution from the Overview tab. The backend does not currently expose saved agent configuration, persistent logs, or agent health metrics.</p>
                <dl className="run-summary">
                  <div><dt>Current workflow</dt><dd>{selectedWorkflow?.label}</dd></div>
                  <div><dt>Provider context</dt><dd>{provider.toUpperCase()}</dd></div>
                  <div><dt>Target resource</dt><dd>{targetResource || "Set when you start a run"}</dd></div>
                  <div><dt>Environment</dt><dd>{activeEnvironment?.name}</dd></div>
                </dl>
                <p className="data-note">Edit provider and target inputs in the Overview form before starting a run. These values are not persisted between sessions.</p>
              </section>
            <p className="data-note adapter-note">
              Local development uses deterministic MCP tools. Live cloud evidence requires configured provider adapters; results are never substituted with preview data.
            </p>
          </ContextGuard>
        </main>
      </div>
    </div>
  </div>
  );
}
