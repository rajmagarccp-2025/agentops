"use client";

import { useWorkspace } from "../state/workspace-context";

export function GlobalContextSelector() {
  const {
    organizations,
    activeOrg,
    projects,
    activeProject,
    environments,
    activeEnvironment,
    setActiveOrg,
    setActiveProject,
    setActiveEnvironment,
    effectiveRole,
    isLoading,
  } = useWorkspace();

  const currentRole = activeEnvironment?.role || activeProject?.role || activeOrg?.role || effectiveRole || "Viewer";
  const assignedScope = activeEnvironment ? "ENVIRONMENT SCOPE" : activeProject ? "PROJECT SCOPE" : "ORGANIZATION SCOPE";

  return (
    <div
      style={{
        background: "#08101e",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "10px",
        padding: "12px 18px",
        marginBottom: "24px",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "14px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span style={{ fontSize: "15px" }}>⚙️</span>
        <span style={{ fontSize: "13px", fontWeight: "700", color: "#ffffff", letterSpacing: "-0.01em" }}>
          Global Context Selector:
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "14px" }}>
        {/* Organization Selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#94a3b8", textTransform: "uppercase" }}>
            Organization
          </label>
          <select
            aria-label="Active organization"
            value={activeOrg?.id ?? ""}
            disabled={isLoading || organizations.length === 0}
            onChange={(e) => {
              const org = organizations.find((o) => o.id === e.target.value);
              if (org) void setActiveOrg(org);
            }}
            style={{
              padding: "6px 12px",
              background: "#1e293b",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "6px",
              color: "#ffffff",
              fontSize: "13px",
              fontWeight: "600",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </div>

        <span style={{ color: "#475569", fontSize: "16px" }}>→</span>

        {/* Project Selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#94a3b8", textTransform: "uppercase" }}>
            Project
          </label>
          <select
            aria-label="Active project"
            value={activeProject?.id ?? ""}
            disabled={isLoading || !activeOrg || projects.length === 0}
            onChange={(e) => {
              const proj = projects.find((p) => p.id === e.target.value);
              if (proj) void setActiveProject(proj);
            }}
            style={{
              padding: "6px 12px",
              background: "#1e293b",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "6px",
              color: "#ffffff",
              fontSize: "13px",
              fontWeight: "600",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {projects.map((proj) => (
              <option key={proj.id} value={proj.id}>
                {proj.name}
              </option>
            ))}
          </select>
        </div>

        <span style={{ color: "#475569", fontSize: "16px" }}>→</span>

        {/* Environment Selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#94a3b8", textTransform: "uppercase" }}>
            Environment
          </label>
          <select
            aria-label="Active environment"
            value={activeEnvironment?.id ?? ""}
            disabled={isLoading || !activeProject || environments.length === 0}
            onChange={(e) => {
              const env = environments.find((ev) => ev.id === e.target.value);
              if (env) void setActiveEnvironment(env);
            }}
            style={{
              padding: "6px 12px",
              background: "#1e293b",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "6px",
              color: "#ffffff",
              fontSize: "13px",
              fontWeight: "600",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
        </div>

        {/* Scope Hierarchy Badge */}
        {/* Scope Hierarchy Badge */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            SCOPE HIERARCHY
          </label>
          <div
            style={{
              padding: "6px 14px",
              background: "rgba(16, 185, 129, 0.12)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              borderRadius: "6px",
              color: "#34d399",
              fontSize: "12px",
              fontWeight: "600",
              fontFamily: "'DM Mono', monospace",
            }}
          >
            {activeEnvironment ? "Environment Scope" : activeProject ? "Project Scope" : "Organization Scope"}
          </div>
        </div>

        {/* Effective role badge */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={{ fontSize: "10px", fontFamily: "'DM Mono', monospace", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            ROLE (PROJECT-LEVEL)
          </label>
          <div
            style={{
              padding: "6px 14px",
              background: "#1e293b",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "6px",
              color: "#ffffff",
              fontSize: "12px",
              fontWeight: "600",
            }}
          >
            {currentRole}
          </div>
        </div>
      </div>
    </div>
  );
}
