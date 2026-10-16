"use client";

import React, { useEffect, useState } from "react";

interface EnvironmentItem {
  id: string;
  name: string;
  slug: string;
  type: string;
  description?: string;
}

interface ProjectItem {
  id: string;
  name: string;
  slug: string;
  description?: string;
  environments: EnvironmentItem[];
}

interface MemberItem {
  user_id: string;
  email: string;
  name: string;
  role: string;
  is_owner: boolean;
}

interface AgentItem {
  id: string;
  name: string;
  type: string;
  status: string;
  autonomy_level: string;
}

interface OrgHierarchy {
  id: string;
  name: string;
  slug: string;
  description?: string;
  users: MemberItem[];
  roles: Array<{ name: string; description: string }>;
  projects: ProjectItem[];
  agents: AgentItem[];
}

export function HierarchyViewer() {
  const [hierarchies, setHierarchies] = useState<OrgHierarchy[]>([]);
  const [activeOrgIndex, setActiveOrgIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    users: true,
    roles: false,
    projects: true,
    agents: true,
  });

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setLoadError(null);

    async function loadHierarchy() {
      try {
        const response = await fetch("/api/proxy/organizations/hierarchy", { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.detail || `Unable to load organization hierarchy (${response.status}).`);
        }
        const data: unknown = await response.json();
        if (!Array.isArray(data)) throw new Error("The organization hierarchy service returned an invalid response.");
        setHierarchies(data);
        setActiveOrgIndex(0);
      } catch (err: unknown) {
        if (!controller.signal.aborted) {
          setHierarchies([]);
          setLoadError(err instanceof Error ? err.message : "Unable to load organization hierarchy.");
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }

    void loadHierarchy();
    return () => controller.abort();
  }, [retryCount]);

  const toggleNode = (nodeKey: string) => {
    setExpandedNodes((prev) => ({ ...prev, [nodeKey]: !prev[nodeKey] }));
  };

  if (isLoading) {
    return (
      <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8" }}>
        Loading Multi-Tenancy Hierarchy...
      </div>
    );
  }

  if (loadError) {
    return (
      <section className="panel error-panel" role="alert">
        <p>{loadError}</p>
        <button type="button" className="btn btn-secondary" onClick={() => setRetryCount((count) => count + 1)}>
          Retry loading hierarchy
        </button>
      </section>
    );
  }

  if (hierarchies.length === 0) {
    return <p className="empty-state">No organization hierarchy is available for this workspace.</p>;
  }

  const currentOrg = hierarchies[activeOrgIndex];

  return (
    <div
      style={{
        background: "#0f172a",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        borderRadius: "16px",
        overflow: "hidden",
        boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
      }}
    >
      {/* Organization Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          background: "#1e293b",
          padding: "8px 16px",
          gap: "8px",
          overflowX: "auto",
        }}
      >
        {hierarchies.map((org, idx) => (
          <button
            key={org.id}
            onClick={() => setActiveOrgIndex(idx)}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: "700",
              border: "none",
              cursor: "pointer",
              background: idx === activeOrgIndex ? "rgba(16, 185, 129, 0.2)" : "transparent",
              color: idx === activeOrgIndex ? "#34d399" : "#94a3b8",
              borderBottom: idx === activeOrgIndex ? "2px solid #10b981" : "2px solid transparent",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span>🏢</span>
            <span>{org.name}</span>
          </button>
        ))}
      </div>

      {/* Main Hierarchy Tree Display */}
      <div style={{ padding: "28px" }}>
        <div style={{ marginBottom: "24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <h3 style={{ margin: 0, fontSize: "20px", fontWeight: "800", color: "#ffffff" }}>
              {currentOrg.name}
            </h3>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "4px",
                background: "rgba(16, 185, 129, 0.15)",
                color: "#34d399",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              Tenant ID: {currentOrg.slug}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
            {currentOrg.description || "Enterprise tenant boundary with isolated encryption and RBAC scoping."}
          </p>
        </div>

        {/* Tree Nodes */}
        <div style={{ display: "grid", gap: "16px" }}>
          {/* Node 1: Users & Access Scopes */}
          <div
            style={{
              background: "rgba(255, 255, 255, 0.02)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              borderRadius: "10px",
              padding: "16px",
            }}
          >
            <div
              onClick={() => toggleNode("users")}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "16px" }}>👥</span>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "#e2e8f0" }}>
                  Users & Subject Identity Mappings ({currentOrg.users?.length || 0})
                </span>
              </div>
              <span style={{ color: "#64748b", fontSize: "12px" }}>
                {expandedNodes.users ? "▲ Hide" : "▼ Show"}
              </span>
            </div>

            {expandedNodes.users && (
              <div style={{ marginTop: "14px", display: "grid", gap: "8px" }}>
                {currentOrg.users?.map((u) => (
                  <div
                    key={u.user_id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "rgba(255, 255, 255, 0.02)",
                      borderRadius: "6px",
                      border: "1px solid rgba(255, 255, 255, 0.04)",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: "600", color: "#f8fafc" }}>
                        {u.name} {u.is_owner && <span style={{ color: "#f59e0b", fontSize: "11px" }}>★ Owner</span>}
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "'DM Mono', monospace" }}>
                        {u.email}
                      </div>
                    </div>
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: "4px",
                        fontSize: "10px",
                        fontWeight: "700",
                        fontFamily: "'DM Mono', monospace",
                        background:
                          u.role === "ADMIN"
                            ? "rgba(239, 68, 68, 0.15)"
                            : u.role === "WRITE"
                            ? "rgba(245, 158, 11, 0.15)"
                            : "rgba(59, 130, 246, 0.15)",
                        color:
                          u.role === "ADMIN"
                            ? "#fca5a5"
                            : u.role === "WRITE"
                            ? "#fcd34d"
                            : "#93c5fd",
                        border: `1px solid ${
                          u.role === "ADMIN"
                            ? "rgba(239, 68, 68, 0.3)"
                            : u.role === "WRITE"
                            ? "rgba(245, 158, 11, 0.3)"
                            : "rgba(59, 130, 246, 0.3)"
                        }`,
                      }}
                    >
                      {u.role}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Node 2: Projects & Environments */}
          <div
            style={{
              background: "rgba(255, 255, 255, 0.02)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              borderRadius: "10px",
              padding: "16px",
            }}
          >
            <div
              onClick={() => toggleNode("projects")}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "16px" }}>📁</span>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "#e2e8f0" }}>
                  Projects & Scoped Environments ({currentOrg.projects?.length || 0})
                </span>
              </div>
              <span style={{ color: "#64748b", fontSize: "12px" }}>
                {expandedNodes.projects ? "▲ Hide" : "▼ Show"}
              </span>
            </div>

            {expandedNodes.projects && (
              <div style={{ marginTop: "14px", display: "grid", gap: "12px" }}>
                {currentOrg.projects?.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      padding: "12px",
                      background: "rgba(255, 255, 255, 0.02)",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: "700", color: "#38bdf8", marginBottom: "4px" }}>
                      Project: {p.name} <span style={{ color: "#64748b", fontSize: "11px" }}>({p.slug})</span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "8px" }}>
                      {p.environments?.map((env) => (
                        <div
                          key={env.id}
                          style={{
                            padding: "6px 12px",
                            borderRadius: "6px",
                            background: "rgba(0, 0, 0, 0.3)",
                            border: "1px solid rgba(255, 255, 255, 0.08)",
                            fontSize: "12px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <span
                            style={{
                              width: "6px",
                              height: "6px",
                              borderRadius: "50%",
                              background:
                                env.type === "Production"
                                  ? "#10b981"
                                  : env.type === "Staging"
                                  ? "#f59e0b"
                                  : "#60a5fa",
                            }}
                          />
                          <span style={{ fontWeight: "600", color: "#e2e8f0" }}>{env.name}</span>
                          <span style={{ color: "#64748b", fontSize: "10px", fontFamily: "'DM Mono', monospace" }}>
                            [{env.type}]
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Node 3: Autonomous AI Agents */}
          <div
            style={{
              background: "rgba(255, 255, 255, 0.02)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              borderRadius: "10px",
              padding: "16px",
            }}
          >
            <div
              onClick={() => toggleNode("agents")}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "16px" }}>🤖</span>
                <span style={{ fontSize: "14px", fontWeight: "700", color: "#e2e8f0" }}>
                  Autonomous SRE & FinOps Agents ({currentOrg.agents?.length || 0})
                </span>
              </div>
              <span style={{ color: "#64748b", fontSize: "12px" }}>
                {expandedNodes.agents ? "▲ Hide" : "▼ Show"}
              </span>
            </div>

            {expandedNodes.agents && (
              <div style={{ marginTop: "14px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "10px" }}>
                {currentOrg.agents?.map((ag) => (
                  <div
                    key={ag.id}
                    style={{
                      padding: "10px 12px",
                      background: "rgba(16, 185, 129, 0.05)",
                      borderRadius: "6px",
                      border: "1px solid rgba(16, 185, 129, 0.15)",
                    }}
                  >
                    <div style={{ fontSize: "12px", fontWeight: "700", color: "#34d399", marginBottom: "2px" }}>
                      ● {ag.name}
                    </div>
                    <div style={{ fontSize: "11px", color: "#94a3b8" }}>{ag.autonomy_level}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
