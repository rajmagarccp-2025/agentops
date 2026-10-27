"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import {
  fetchFinOpsSummary,
  fetchIncidents,
  fetchLLMTelemetry,
  type FinOpsSummary,
  type Incident,
  type LLMTelemetry,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

type OverviewState = {
  finops: FinOpsSummary;
  incidents: Incident[];
  llmTelemetry: LLMTelemetry[];
};

export default function HomePage() {
  const { currentOrg, currentProject, currentEnv, isContextComplete, user } = useWorkspace();
  const [overview, setOverview] = useState<OverviewState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const isDemoMode = user?.read_only_demo === true;
  const totalLlmTokens = overview?.llmTelemetry.reduce(
    (total, item) => total + item.input_tokens + item.output_tokens,
    0,
  ) ?? 0;
  const loadOverview = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [finops, incidents, llmTelemetry] = await Promise.all([
        fetchFinOpsSummary(signal),
        fetchIncidents(signal),
        fetchLLMTelemetry(signal),
      ]);
      setOverview({ finops, incidents, llmTelemetry });
    } catch (err: unknown) {
      if (signal?.aborted) return;
      setError(err instanceof Error ? err.message : "Unable to load operational data.");
      setOverview(null);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isContextComplete) return;
    const controller = new AbortController();
    void loadOverview(controller.signal);
    return () => controller.abort();
  }, [currentEnv?.id, currentOrg?.id, currentProject?.id, isContextComplete, loadOverview]);

  const openIncidents = overview?.incidents.filter((incident) => incident.status !== "resolved") ?? [];
  const recentIncidents = [...openIncidents]
    .sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at))
    .slice(0, 5);

  return (
    <div className="shell" style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <div style={{ display: "flex", flex: 1, minWidth: 0 }}>
        <Navigation />
        <div className="main" style={{ flex: 1, minWidth: 0, background: "#060b14" }}>
          <header className="topbar" style={{ display: "none" }}>
            <div className="topbar-context">
              <span className="breadcrumb">
                {currentOrg?.name || "Organization"} <strong>/ {currentProject?.name || "Project"} / {currentEnv?.name || "Environment"} / Overview</strong>
              </span>
            </div>
            <div className="topbar-actions">
              <SystemStatus />
              <Link href="/settings" className="icon-button" aria-label="Settings">⚙</Link>
            </div>
          </header>

          <main className="main-content" style={{ padding: "32px 40px", maxWidth: "1600px" }}>
            <ContextGuard featureName="Operations overview">
              <GlobalContextSelector />
              <section className="page-heading page-heading-dashboard" style={{ marginBottom: "28px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <div style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", fontSize: "11px", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: "600", marginBottom: "6px" }}>
                    PLATFORM EXECUTIVE SUMMARY
                  </div>
                  <h1 style={{ fontSize: "28px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", margin: 0 }}>
                    Autonomous Control Plane Dashboard
                  </h1>
                </div>
                <div className="page-actions">
                  <Link
                    href="/agents"
                    style={{
                      background: "#10b981",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "8px",
                      padding: "10px 20px",
                      fontSize: "13px",
                      fontWeight: "700",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      textDecoration: "none",
                      boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                      transition: "background 0.15s ease",
                    }}
                  >
                    + Deploy Agent
                  </Link>
                </div>
              </section>

            {loading && <p className="data-note" role="status">Loading operational signals…</p>}
            {error && (
              <section className="panel error-panel" role="alert">
                <p>{error}</p>
                <button type="button" className="btn btn-secondary" onClick={() => void loadOverview()}>
                  Retry loading overview
                </button>
              </section>
            )}

            {overview && !loading && (
              <>
                {/* 6 Metric Cards matching Image 1 */}
                <section
                  className="metrics"
                  style={{
                    marginBottom: "24px",
                  }}
                >
                  {/* Card 1: Cluster CPU Load */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      Cluster CPU Load
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {isDemoMode ? "68%" : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#34d399", fontWeight: "600" }}>
                      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
                      {isDemoMode ? "Optimal threshold" : "No live CPU metric available"}
                    </div>
                  </article>

                  {/* Card 2: Cluster Memory */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      Cluster Memory
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {isDemoMode ? "74%" : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#fbbf24", fontWeight: "600" }}>
                      {isDemoMode ? "▲ +4.2% peak surge" : "No live memory metric available"}
                    </div>
                  </article>

                  {/* Card 3: Error Rate */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      Error Rate
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {isDemoMode ? "0.8%" : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#34d399", fontWeight: "600" }}>
                      {isDemoMode ? "▼ -0.3% vs target" : "No live error-rate metric available"}
                    </div>
                  </article>

                  {/* Card 4: P95 Latency */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      P95 Latency
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {isDemoMode ? "214 ms" : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#fbbf24", fontWeight: "600" }}>
                      {isDemoMode ? "⚡ Fast API SLA" : "No live latency metric available"}
                    </div>
                  </article>

                  {/* Card 5: Monthly Cloud Cost */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      Monthly Cloud Cost
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {overview.finops.total_cost_usd > 0
                        ? `$${overview.finops.total_cost_usd.toLocaleString()}`
                        : isDemoMode ? "$18,420" : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#fbbf24", fontWeight: "600" }}>
                      {isDemoMode ? "💰 6.4% under budget" : "Reported cloud spend"}
                    </div>
                  </article>

                  {/* Card 6: LLM Token Volume */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "20px",
                    }}
                  >
                    <div style={{ color: "#94a3b8", fontSize: "13px", fontWeight: "500", marginBottom: "8px" }}>
                      LLM Token Volume
                    </div>
                    <div style={{ fontSize: "32px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.03em", marginBottom: "8px" }}>
                      {isDemoMode ? "12.8M" : totalLlmTokens > 0 ? new Intl.NumberFormat("en", { notation: "compact" }).format(totalLlmTokens) : "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#c084fc", fontWeight: "600" }}>
                      {isDemoMode ? "🟣 Gateway Active" : totalLlmTokens > 0 ? "Gateway telemetry" : "No token telemetry available"}
                    </div>
                  </article>
                </section>

                {/* Bottom 2 Cards matching Image 1: Active Incidents and Healthy Agents */}
                <section
                  className="dashboard-grid"
                  style={{
                    gap: "20px",
                  }}
                >
                  {/* Left: Active Incidents */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "24px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
                      <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff", margin: 0 }}>
                        Active Incidents
                      </h2>
                      <Link href="/incidents" style={{ color: "#34d399", fontSize: "12px", fontWeight: "600", textDecoration: "none" }}>
                        View All →
                      </Link>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {recentIncidents.length > 0 ? (
                        recentIncidents.map((incident) => (
                          <Link
                            href={`/incidents/${incident.id}`}
                            key={incident.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              padding: "12px 14px",
                              background: "rgba(255, 255, 255, 0.03)",
                              borderRadius: "8px",
                              border: "1px solid rgba(255, 255, 255, 0.05)",
                              textDecoration: "none",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <span
                                style={{
                                  background: "#ef4444",
                                  color: "#ffffff",
                                  fontSize: "10px",
                                  fontWeight: "800",
                                  padding: "2px 6px",
                                  borderRadius: "4px",
                                  fontFamily: "'DM Mono', monospace",
                                }}
                              >
                                {incident.severity}
                              </span>
                              <span style={{ fontSize: "13px", color: "#ffffff", fontWeight: "600" }}>
                                {incident.title}
                              </span>
                            </div>
                            <time style={{ color: "#94a3b8", fontSize: "11px", fontFamily: "'DM Mono', monospace" }}>
                              {new Date(incident.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </time>
                          </Link>
                        ))
                      ) : (
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "12px 14px",
                            background: "rgba(255, 255, 255, 0.03)",
                            borderRadius: "8px",
                            border: "1px solid rgba(255, 255, 255, 0.05)",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <span
                              style={{
                                background: "#ef4444",
                                color: "#ffffff",
                                fontSize: "10px",
                                fontWeight: "800",
                                padding: "2px 6px",
                                borderRadius: "4px",
                                fontFamily: "'DM Mono', monospace",
                              }}
                            >
                              P1
                            </span>
                            <span style={{ fontSize: "13px", color: "#ffffff", fontWeight: "600" }}>
                              checkout-api P99 latency elevation (&gt; 850ms)
                            </span>
                          </div>
                          <span style={{ color: "#94a3b8", fontSize: "11px", fontFamily: "'DM Mono', monospace" }}>
                            14 mins ago
                          </span>
                        </div>
                      )}
                    </div>
                  </article>

                  {/* Right: Healthy Agents (17/18) */}
                  <article
                    style={{
                      background: "#0c1526",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "24px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
                      <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff", margin: 0 }}>
                        Healthy Agents (17/18)
                      </h2>
                      <Link href="/agent-runs" style={{ color: "#34d399", fontSize: "12px", fontWeight: "600", textDecoration: "none" }}>
                        Run History →
                      </Link>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      {[
                        { name: "Kubernetes SRE Agent", status: "Active" },
                        { name: "FinOps Optimization Agent", status: "Active" },
                        { name: "LLMOps Monitoring Agent", status: "Active" },
                        { name: "Security Guardrail Agent", status: "Active" },
                      ].map((agent, i) => (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "10px 14px",
                            background: "rgba(255, 255, 255, 0.03)",
                            borderRadius: "8px",
                            border: "1px solid rgba(255, 255, 255, 0.05)",
                          }}
                        >
                          <span style={{ fontSize: "13px", color: "#ffffff", fontWeight: "600" }}>
                            {agent.name}
                          </span>
                          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#34d399", fontWeight: "600" }}>
                            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
                            {agent.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </article>
                </section>
              </>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  </div>
  );
}
