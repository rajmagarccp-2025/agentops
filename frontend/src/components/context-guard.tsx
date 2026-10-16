"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useWorkspace } from "../state/workspace-context";

interface ContextGuardProps {
  children: React.ReactNode;
  featureName?: string;
  permission?: string;
}

export function ContextGuard({ children, featureName = "AgentOps features", permission }: ContextGuardProps) {
  const {
    activeOrg,
    activeProject,
    activeEnvironment,
    projects,
    environments,
    setActiveProject,
    setActiveEnvironment,
    isLoading,
    workspaceError,
    refreshWorkspace,
    permissions,
    effectiveRole,
  } = useWorkspace();

  const [isCreatingEnv, setIsCreatingEnv] = useState(false);
  const [newEnvName, setNewEnvName] = useState("Development");
  const [newEnvType, setNewEnvType] = useState("Development");
  const [envLoading, setEnvLoading] = useState(false);
  const [envError, setEnvError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8", fontFamily: "'Manrope', sans-serif" }}>
        <div style={{ display: "inline-block", width: "24px", height: "24px", border: "2px solid #10b981", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <div style={{ marginTop: "12px", fontSize: "13px" }}>Verifying tenancy context & cryptographic isolation...</div>
      </div>
    );
  }

  if (workspaceError) {
    return (
      <section className="workspace-error" role="alert" aria-live="polite">
        <h2>Workspace context could not be verified</h2>
        <p>{workspaceError}</p>
        <button type="button" className="btn btn-secondary" onClick={() => void refreshWorkspace()}>
          Retry workspace connection
        </button>
      </section>
    );
  }

  // Case 1: No Organization Selected
  if (!activeOrg) {
    return (
      <div
        style={{
          maxWidth: "600px",
          margin: "40px auto",
          background: "#0f172a",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "16px",
          padding: "36px",
          textAlign: "center",
          color: "#f8fafc",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
        }}
      >
        <div style={{ fontSize: "36px", marginBottom: "16px" }}>🏢</div>
        <h2 style={{ fontSize: "20px", fontWeight: "800", margin: "0 0 8px 0" }}>
          Organization Context Required
        </h2>
        <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: 1.6, margin: "0 0 24px 0" }}>
          To access <strong>{featureName}</strong>, you must select or create an Organization. All telemetry,
          agents, and data are strictly isolated by organization tenancy.
        </p>
        <Link
          href="/onboarding"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 24px",
            background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
            color: "#ffffff",
            borderRadius: "8px",
            fontWeight: "700",
            fontSize: "13px",
            textDecoration: "none",
          }}
        >
          <span>Go to Organization Setup</span>
          <span>→</span>
        </Link>
      </div>
    );
  }

  // Case 2: Organization selected but No Project Selected
  if (!activeProject) {
    return (
      <div
        style={{
          maxWidth: "640px",
          margin: "40px auto",
          background: "#0f172a",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "16px",
          padding: "36px",
          color: "#f8fafc",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>📁</div>
          <h2 style={{ fontSize: "20px", fontWeight: "800", margin: "0 0 8px 0" }}>
            Select or Create a Project
          </h2>
          <p style={{ fontSize: "13px", color: "#94a3b8", margin: 0 }}>
            Active Organization: <strong style={{ color: "#34d399" }}>{activeOrg.name}</strong>
          </p>
        </div>

        {projects.length > 0 ? (
          <div>
            <div style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "10px", fontWeight: "600", textTransform: "uppercase" }}>
              Available Projects in {activeOrg.name}:
            </div>
            <div style={{ display: "grid", gap: "10px", marginBottom: "24px" }}>
              {projects.map((proj) => (
                <button
                  type="button"
                  key={proj.id}
                  onClick={() => void setActiveProject(proj)}
                  style={{
                    display: "flex",
                    width: "100%",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 16px",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    color: "#f8fafc",
                    textAlign: "left",
                  }}
                >
                  <div>
                    <strong style={{ fontSize: "14px" }}>{proj.name}</strong>
                    <div style={{ fontSize: "11px", color: "#94a3b8" }}>{proj.description || "Project workspace"}</div>
                  </div>
                  <span style={{ color: "#34d399", fontSize: "12px", fontWeight: "700" }}>Select Project →</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "16px 0 24px", color: "#94a3b8", fontSize: "13px" }}>
            No projects exist yet in <strong>{activeOrg.name}</strong>. Create your first project to get started.
          </div>
        )}

        <div style={{ textAlign: "center", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "20px" }}>
          <Link
            href="/projects"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
              color: "#ffffff",
              borderRadius: "8px",
              fontWeight: "700",
              fontSize: "13px",
              textDecoration: "none",
            }}
          >
            <span>+ Create New Project</span>
          </Link>
        </div>
      </div>
    );
  }

  // Case 3: Project selected but No Environment Selected
  if (!activeEnvironment) {
    const handleCreateEnv = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!newEnvName.trim()) return;
      setEnvLoading(true);
      setEnvError(null);
      try {
        const res = await fetch(`/api/proxy/projects/${activeProject.id}/environments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: newEnvName.trim(),
            type: newEnvType,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `Environment creation failed (${res.status}).`);
        }
        const envData = await res.json();
        await setActiveEnvironment(envData);
        setIsCreatingEnv(false);
      } catch (err: unknown) {
        setEnvError(err instanceof Error ? err.message : "Environment creation failed.");
      } finally {
        setEnvLoading(false);
      }
    };

    return (
      <div
        style={{
          maxWidth: "640px",
          margin: "40px auto",
          background: "#0f172a",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "16px",
          padding: "36px",
          color: "#f8fafc",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>🌐</div>
          <h2 style={{ fontSize: "20px", fontWeight: "800", margin: "0 0 8px 0" }}>
            Select an Environment
          </h2>
          <p style={{ fontSize: "13px", color: "#94a3b8", margin: 0 }}>
            {activeOrg.name} <span style={{ color: "#64748b" }}>/</span> {activeProject.name}
          </p>
        </div>

        {environments.length > 0 ? (
          <div>
            <div style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "10px", fontWeight: "600", textTransform: "uppercase" }}>
              Available Environments:
            </div>
            <div style={{ display: "grid", gap: "10px", marginBottom: "24px" }}>
              {environments.map((env) => (
                <button
                  type="button"
                  key={env.id}
                  onClick={() => void setActiveEnvironment(env)}
                  style={{
                    display: "flex",
                    width: "100%",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 16px",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    cursor: "pointer",
                    color: "#f8fafc",
                    textAlign: "left",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span
                      style={{
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: env.type === "Production" ? "#ef4444" : env.type === "Staging" ? "#f59e0b" : "#10b981",
                      }}
                    />
                    <div>
                      <strong style={{ fontSize: "14px" }}>{env.name}</strong>
                      <span style={{ marginLeft: "8px", fontSize: "11px", color: "#94a3b8" }}>({env.type})</span>
                    </div>
                  </div>
                  <span style={{ color: "#34d399", fontSize: "12px", fontWeight: "700" }}>Select Environment →</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "16px 0 24px", color: "#94a3b8", fontSize: "13px" }}>
            No environments found for this project.
          </div>
        )}

        {!isCreatingEnv ? (
          <div style={{ textAlign: "center", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "20px" }}>
            <button
              type="button"
              onClick={() => setIsCreatingEnv(true)}
              style={{
                padding: "10px 20px",
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontWeight: "700",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              + Create Environment (Production / Staging / Dev)
            </button>
          </div>
        ) : (
          <form onSubmit={handleCreateEnv} style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "20px", display: "grid", gap: "12px" }}>
            {envError && <p role="alert" className="data-note warning">{envError}</p>}
            <div style={{ fontSize: "12px", fontWeight: "700", color: "#34d399" }}>Create New Environment:</div>
            <div style={{ display: "flex", gap: "10px" }}>
              <input
                type="text"
                value={newEnvName}
                onChange={(e) => setNewEnvName(e.target.value)}
                placeholder="Environment Name"
                required
                style={{ flex: 1, padding: "8px 12px", borderRadius: "6px", background: "rgba(255, 255, 255, 0.05)", border: "1px solid rgba(255, 255, 255, 0.15)", color: "#ffffff", fontSize: "13px" }}
              />
              <select
                value={newEnvType}
                onChange={(e) => setNewEnvType(e.target.value)}
                style={{ padding: "8px 12px", borderRadius: "6px", background: "#1e293b", border: "1px solid rgba(255, 255, 255, 0.15)", color: "#ffffff", fontSize: "13px" }}
              >
                <option value="Production">Production</option>
                <option value="Staging">Staging</option>
                <option value="Development">Development</option>
                <option value="QA">QA</option>
              </select>
            </div>
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setIsCreatingEnv(false)}
                style={{ padding: "6px 12px", background: "transparent", border: "1px solid rgba(255, 255, 255, 0.15)", borderRadius: "6px", color: "#94a3b8", fontSize: "12px", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={envLoading}
                style={{ padding: "6px 16px", background: "#10b981", border: "none", borderRadius: "6px", color: "#ffffff", fontSize: "12px", fontWeight: "700", cursor: "pointer" }}
              >
                {envLoading ? "Creating..." : "Save & Activate"}
              </button>
            </div>
          </form>
        )}
      </div>
    );
  }

  if (permission && !permissions.hasPermission(permission)) {
    return (
      <section className="workspace-error" role="alert">
        <h2>Access unavailable</h2>
        <p>
          Your effective role, {effectiveRole}, does not include <code>{permission}</code> access for {featureName}.
          Contact an organization administrator if you need this capability.
        </p>
      </section>
    );
  }

  // All 3 contexts are selected! Render children
  return <>{children}</>;
}
