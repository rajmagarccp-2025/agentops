"use client";

import React, { useState } from "react";
import { useWorkspace } from "../state/workspace-context";

interface StreamStep {
  node: string;
  status: string;
  recommendation?: string;
  structured_findings?: Array<Record<string, unknown>>;
  hypotheses?: Array<Record<string, unknown>>;
  confidence?: number;
}

export function AICopilotBox() {
  const { activeOrg, activeProject, activeEnvironment, permissions } = useWorkspace();
  const [mode, setMode] = useState<"query" | "agent_stream">("agent_stream");
  const [agentType, setAgentType] = useState<string>("sre");
  const [query, setQuery] = useState("Investigate elevated p99 latency on checkout-api and suggest root cause");
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<string | null>(null);
  const [streamSteps, setStreamSteps] = useState<StreamStep[]>([]);
  const [finalRecommendation, setFinalRecommendation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canExecuteAI = permissions.canAskAI();

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrg || !activeProject || !activeEnvironment) {
      setError("Please select an Organization, Project, and Environment first.");
      return;
    }
    if (!canExecuteAI) {
      setError("Permission denied: READ role cannot submit AI query actions (strict RBAC enforced).");
      return;
    }

    setIsLoading(true);
    setError(null);
    setResponse(null);
    setStreamSteps([]);
    setFinalRecommendation(null);

    if (mode === "query") {
      try {
        const res = await fetch("/api/proxy/ai/query", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-tenant-id": activeOrg.id,
            "x-project-id": activeProject.id,
            "x-environment-id": activeEnvironment.id,
          },
          body: JSON.stringify({
            organization_id: activeOrg.id,
            project_id: activeProject.id,
            environment_id: activeEnvironment.id,
            query,
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "AI query failed");
        }
        setResponse(data.response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error executing AI query";
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    } else {
      // Live Agent Streaming via SSE
      try {
        const res = await fetch("/api/proxy/agent-runs/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-tenant-id": activeOrg.id,
            "x-project-id": activeProject.id,
            "x-environment-id": activeEnvironment.id,
          },
          body: JSON.stringify({
            request: query,
            request_type: agentType,
            cloud_provider: "aws",
            environment: activeEnvironment.type || "production",
            target_resource: "checkout-api",
            project_id: activeProject.id,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: "Streaming request failed" }));
          throw new Error(errData.detail || "Streaming execution failed");
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No readable stream response from agent");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
              const jsonStr = trimmed.replace("data:", "").trim();
              if (jsonStr) {
                try {
                  const eventData = JSON.parse(jsonStr);
                  if (eventData.event === "node_update") {
                    setStreamSteps((prev) => [
                      ...prev,
                      {
                        node: eventData.node,
                        status: eventData.status,
                        recommendation: eventData.recommendation,
                        structured_findings: eventData.structured_findings,
                        hypotheses: eventData.hypotheses,
                        confidence: eventData.confidence,
                      },
                    ]);
                  } else if (eventData.event === "complete") {
                    setFinalRecommendation(eventData.recommendation || "Workflow completed successfully.");
                  } else if (eventData.event === "error") {
                    setError(`Agent execution failed: ${eventData.error}`);
                  }
                } catch {
                  // ignore JSON parse error on incomplete chunks
                }
              }
            }
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error streaming agent execution";
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <article
      className="panel panel-wide"
      style={{
        background: "linear-gradient(180deg, rgba(21, 92, 67, 0.1) 0%, rgba(15, 23, 42, 0.5) 100%)",
        border: "1px solid rgba(52, 211, 153, 0.25)",
        borderRadius: "12px",
        padding: "22px",
        marginBottom: "24px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <h2 style={{ fontSize: "16px", margin: "0 0 4px 0", color: "#f8fafc", display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🤖 Autonomous Specialist Agent Intelligence</span>
            <span style={{ fontSize: "10px", background: "rgba(16, 185, 129, 0.2)", color: "#34d399", padding: "2px 6px", borderRadius: "4px", fontFamily: "'DM Mono', monospace" }}>
              PART 2 ACTIVE
            </span>
          </h2>
          <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8" }}>
            Real-time LangGraph execution scoped to:{" "}
            <strong style={{ color: "#34d399" }}>
              {activeOrg?.name || "No Org"} / {activeProject?.name || "No Project"} / {activeEnvironment?.name || "No Env"}
            </strong>
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {!canExecuteAI ? (
            <span
              style={{
                fontSize: "11px",
                background: "rgba(239, 68, 68, 0.15)",
                color: "#f87171",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                padding: "4px 10px",
                borderRadius: "4px",
                fontFamily: "'DM Mono', monospace",
              }}
            >
              🔒 READ-ONLY (AI Actions Guarded)
            </span>
          ) : (
            <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.05)", borderRadius: "6px", padding: "2px" }}>
              <button
                type="button"
                onClick={() => setMode("agent_stream")}
                style={{
                  border: "none",
                  background: mode === "agent_stream" ? "#155c43" : "transparent",
                  color: mode === "agent_stream" ? "#ffffff" : "#94a3b8",
                  padding: "4px 10px",
                  borderRadius: "4px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                ⚡ Live Agent Stream
              </button>
              <button
                type="button"
                onClick={() => setMode("query")}
                style={{
                  border: "none",
                  background: mode === "query" ? "#155c43" : "transparent",
                  color: mode === "query" ? "#ffffff" : "#94a3b8",
                  padding: "4px 10px",
                  borderRadius: "4px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Direct Copilot
              </button>
            </div>
          )}
        </div>
      </div>

      <form onSubmit={handleQuerySubmit}>
        {mode === "agent_stream" && (
          <div style={{ display: "flex", gap: "8px", marginBottom: "12px", alignItems: "center" }}>
            <span style={{ fontSize: "11px", color: "#94a3b8", fontFamily: "'DM Mono', monospace" }}>
              SELECT SPECIALIST AGENT:
            </span>
            {[
              { id: "sre", label: "SRE / Incident" },
              { id: "finops", label: "FinOps Cost" },
              { id: "change", label: "Change Diff" },
              { id: "security", label: "Security IAM" },
              { id: "discovery", label: "Discovery" },
              { id: "llmops", label: "LLMOps Telemetry" },
            ].map((spec) => (
              <button
                key={spec.id}
                type="button"
                onClick={() => setAgentType(spec.id)}
                style={{
                  border: agentType === spec.id ? "1px solid #34d399" : "1px solid rgba(255, 255, 255, 0.1)",
                  background: agentType === spec.id ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.03)",
                  color: agentType === spec.id ? "#34d399" : "#94a3b8",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  fontSize: "10px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {spec.label}
              </button>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: "10px" }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={!canExecuteAI || isLoading}
            placeholder={
              canExecuteAI
                ? "Describe SRE incident, performance bottleneck, or FinOps goal..."
                : "READ role: Interactive AI execution is disabled by organization policy."
            }
            style={{
              flex: 1,
              padding: "10px 14px",
              background: "rgba(15, 23, 42, 0.8)",
              border: !canExecuteAI ? "1px dashed rgba(239, 68, 68, 0.4)" : "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              color: !canExecuteAI ? "#94a3b8" : "#f8fafc",
              fontSize: "13px",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={!canExecuteAI || isLoading}
            id="submit-ai-query-btn"
            style={{
              padding: "10px 18px",
              background: !canExecuteAI ? "#334155" : "#155c43",
              color: "#ffffff",
              border: "0",
              borderRadius: "8px",
              fontWeight: "700",
              fontSize: "12px",
              cursor: !canExecuteAI || isLoading ? "not-allowed" : "pointer",
              opacity: !canExecuteAI ? 0.6 : 1,
              whiteSpace: "nowrap",
            }}
          >
            {isLoading ? "Executing Agent..." : mode === "agent_stream" ? "Run Agent Stream ⚡" : "Execute Copilot →"}
          </button>
        </div>
      </form>

      {error && (
        <div
          style={{
            marginTop: "12px",
            padding: "10px 14px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "6px",
            color: "#f87171",
            fontSize: "12px",
          }}
        >
          <strong>Authorization Policy Alert:</strong> {error}
        </div>
      )}

      {/* Live Stream Step Progress */}
      {streamSteps.length > 0 && (
        <div
          style={{
            marginTop: "16px",
            padding: "14px",
            background: "rgba(15, 23, 42, 0.9)",
            border: "1px solid rgba(52, 211, 153, 0.2)",
            borderRadius: "8px",
          }}
        >
          <div style={{ fontSize: "11px", fontWeight: "700", color: "#34d399", marginBottom: "10px", fontFamily: "'DM Mono', monospace" }}>
            ● LIVE LANGGRAPH NODE EXECUTION STREAM:
          </div>

          <div style={{ display: "grid", gap: "8px" }}>
            {streamSteps.map((step, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  fontSize: "12px",
                  padding: "6px 8px",
                  background: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "4px",
                }}
              >
                <span className="status-dot" style={{ marginTop: "4px" }} />
                <div style={{ flex: 1 }}>
                  <div>
                    <strong style={{ color: "#ffffff", textTransform: "uppercase", fontSize: "11px" }}>
                      [{step.node}]
                    </strong>{" "}
                    <span style={{ color: "#94a3b8" }}>Status: {step.status}</span>
                  </div>
                  {step.structured_findings && step.structured_findings.length > 0 && (
                    <div style={{ marginTop: "4px", color: "#cbd5e1", fontSize: "11px" }}>
                      Findings: {step.structured_findings.map((f, i) => String(f.title || f.finding || JSON.stringify(f))).join("; ")}
                    </div>
                  )}
                  {step.hypotheses && step.hypotheses.length > 0 && (
                    <div style={{ marginTop: "2px", color: "#a7f3d0", fontSize: "11px" }}>
                      Hypotheses: {step.hypotheses.map((h, i) => String(h.title || h.description || "")).join("; ")}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final Recommendation / Direct Response */}
      {(finalRecommendation || response) && (
        <div
          style={{
            marginTop: "14px",
            padding: "14px 18px",
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "8px",
            fontSize: "13px",
            color: "#e2e8f0",
          }}
        >
          <div style={{ fontSize: "11px", color: "#34d399", fontWeight: "700", marginBottom: "6px" }}>
            ✓ SYNTHESIZED AGENT RECOMMENDATION (Evidence-Backed & Governed):
          </div>
          <div>{finalRecommendation || response}</div>
        </div>
      )}
    </article>
  );
}
