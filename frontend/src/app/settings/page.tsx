"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navigation } from "../../components/navigation";
import { useWorkspace } from "../../state/workspace-context";

interface AuditEvent {
  id: string;
  actor: string;
  actor_email?: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  organization_id?: string | null;
  project_id?: string | null;
  environment_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

type SettingsTab = "org" | "project" | "environment" | "audit";

export default function SettingsPage() {
  const {
    activeOrg,
    currentOrg,
    activeProject,
    activeEnvironment,
    effectiveRole,
    permissions,
    refreshWorkspace,
  } = useWorkspace();

  const [activeTab, setActiveTab] = useState<SettingsTab>("org");
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  // Org form state
  const [orgName, setOrgName] = useState(activeOrg?.name || "");
  const [orgSaved, setOrgSaved] = useState(false);

  // Project form state
  const [projName, setProjName] = useState(activeProject?.name || "");
  const [projSaved, setProjSaved] = useState(false);


  useEffect(() => {
    if (activeOrg?.name) setOrgName(activeOrg.name);
  }, [activeOrg?.name]);

  useEffect(() => {
    if (activeProject?.name) setProjName(activeProject.name);
  }, [activeProject?.name]);

  useEffect(() => {
    if (window.location.hash === "#secrets") {
      setActiveTab("environment");
    }
  }, []);

  useEffect(() => {
    if (activeTab === "environment" && window.location.hash === "#secrets") {
      document.getElementById("secrets")?.scrollIntoView();
    }
  }, [activeTab]);

  useEffect(() => {
    const fetchAudit = async () => {
      const orgId = activeOrg?.id || currentOrg?.id;
      if (!orgId) return;
      setLoadingAudit(true);
      setAuditError(null);
      try {
        const res = await fetch(`/api/proxy/audit-logs?organization_id=${orgId}&limit=50`);
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `Unable to load audit logs (${res.status}).`);
        }
        setLogs(await res.json());
      } catch (err: unknown) {
        setAuditError(err instanceof Error ? err.message : "Unable to load audit logs.");
      } finally {
        setLoadingAudit(false);
      }
    };
    if (activeTab === "audit") {
      fetchAudit();
    }
  }, [activeTab, activeOrg?.id, currentOrg?.id]);

  const handleSaveOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    const organizationId = activeOrg?.id || currentOrg?.id;
    if (!organizationId) return;
    setSavingSettings(true);
    setSettingsError(null);
    try {
      const response = await fetch(`/api/proxy/organizations/${organizationId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: orgName.trim() }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Unable to update organization (${response.status}).`);
      }
      await refreshWorkspace();
      setOrgSaved(true);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "Unable to update organization.");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject?.id) return;
    setSavingSettings(true);
    setSettingsError(null);
    try {
      const response = await fetch(`/api/proxy/projects/${activeProject.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: projName.trim() }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Unable to update project (${response.status}).`);
      }
      await refreshWorkspace();
      setProjSaved(true);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "Unable to update project.");
    } finally {
      setSavingSettings(false);
    }
  };

  const tabButtonStyle = (tab: SettingsTab): React.CSSProperties => ({
    padding: "10px 18px",
    background: activeTab === tab ? "rgba(16, 185, 129, 0.15)" : "transparent",
    border: "none",
    borderBottom: activeTab === tab ? "2px solid #10b981" : "2px solid transparent",
    color: activeTab === tab ? "#34d399" : "#94a3b8",
    fontSize: "13px",
    fontWeight: activeTab === tab ? 700 : 500,
    cursor: "pointer",
    transition: "all 0.2s",
  });

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">
              Workspace <strong>/ {activeOrg?.name || currentOrg?.name || "AgentOps"}</strong> / Settings
            </span>
          </div>
          <div className="topbar-actions">
            <span className={`badge badge-${effectiveRole.toLowerCase()}`}>
              Role: {effectiveRole}
            </span>
          </div>
        </header>

        <main className="main-content">
          <section className="page-heading">
            <div>
              <span className="kicker">Configuration & Governance</span>
              <h1>Settings & Immutable Audit Trail</h1>
              <p className="lede">
                Fine-grained settings isolated by tenancy tier: Organization, Project, and Environment.
              </p>
            </div>
          </section>
          {settingsError && <div className="alert-banner error" role="alert" style={{ marginBottom: "20px" }}>{settingsError}</div>}

          {/* Tab Navigation */}
          <div
            style={{
              display: "flex",
              borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
              marginBottom: "28px",
              gap: "8px",
            }}
          >
            <button style={tabButtonStyle("org")} onClick={() => setActiveTab("org")} id="tab-org-settings">
              🏢 Organization Settings
            </button>
            <button style={tabButtonStyle("project")} onClick={() => setActiveTab("project")} id="tab-project-settings">
              📁 Project Settings
            </button>
            <button style={tabButtonStyle("environment")} onClick={() => setActiveTab("environment")} id="tab-env-settings">
              🌐 Environment Settings
            </button>
            <button style={tabButtonStyle("audit")} onClick={() => setActiveTab("audit")} id="tab-audit-logs">
              📜 Audit Logs
            </button>
          </div>

          {/* TAB 1: ORGANIZATION SETTINGS */}
          {activeTab === "org" && (
            <div style={{ display: "grid", gap: "24px" }}>
              {/* Profile & Identity */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h2 className="card-title">Organization Profile</h2>
                    <div className="card-subtitle">Global organization metadata and root branding</div>
                  </div>
                  <span className={`badge badge-${(activeOrg?.role || effectiveRole).toLowerCase()}`}>
                    Role: {activeOrg?.role || effectiveRole}
                  </span>
                </div>

                <form onSubmit={handleSaveOrg} style={{ display: "grid", gap: "16px", maxWidth: "600px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                      Organization Name
                    </label>
                    <input
                      type="text"
                      value={orgName}
                      onChange={(e) => { setOrgSaved(false); setOrgName(e.target.value); }}
                      disabled={!permissions.canManageOrganization()}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid rgba(255, 255, 255, 0.12)",
                        color: "#ffffff",
                        fontSize: "13px",
                      }}
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                        Organization Slug
                      </label>
                      <input
                        type="text"
                        value={activeOrg?.slug || ""}
                        disabled
                        style={{
                          width: "100%",
                          padding: "10px 14px",
                          borderRadius: "8px",
                          background: "rgba(255, 255, 255, 0.02)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          color: "#94a3b8",
                          fontFamily: "'DM Mono', monospace",
                          fontSize: "12px",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                        Tenant ID (UUID)
                      </label>
                      <input
                        type="text"
                        value={activeOrg?.id || ""}
                        disabled
                        style={{
                          width: "100%",
                          padding: "10px 14px",
                          borderRadius: "8px",
                          background: "rgba(255, 255, 255, 0.02)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          color: "#94a3b8",
                          fontFamily: "'DM Mono', monospace",
                          fontSize: "11px",
                        }}
                      />
                    </div>
                  </div>

                  {permissions.canManageOrganization() && (
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "8px" }}>
                      <button
                        type="submit"
                        className="btn btn-primary"
                        style={{ padding: "8px 20px", fontSize: "13px" }}
                        disabled={savingSettings || !orgName.trim()}
                      >
                        {savingSettings ? "Saving…" : "Save Organization Changes"}
                      </button>
                      {orgSaved && <span style={{ color: "#34d399", fontSize: "12px" }}>✓ Changes saved</span>}
                    </div>
                  )}
                </form>
              </div>

              {/* Members & Roles */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h2 className="card-title">Members & Organization Roles</h2>
                    <div className="card-subtitle">Manage organization-level access and invitation tokens</div>
                  </div>
                  <Link href="/members" className="btn btn-secondary" style={{ fontSize: "12px", padding: "6px 14px" }}>
                    Manage All Members →
                  </Link>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px", fontSize: "12px" }}>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "14px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                    <div style={{ color: "#f59e0b", fontWeight: "700", marginBottom: "4px" }}>Organization Owner</div>
                    <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", lineHeight: 1.5 }}>
                      Full unrestricted control: org settings, billing, member management, project and environment lifecycle.
                    </p>
                  </div>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "14px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                    <div style={{ color: "#60a5fa", fontWeight: "700", marginBottom: "4px" }}>Organization Admin</div>
                    <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", lineHeight: 1.5 }}>
                      Can manage projects, environments, invite members, and configure settings. Cannot transfer ownership.
                    </p>
                  </div>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "14px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                    <div style={{ color: "#34d399", fontWeight: "700", marginBottom: "4px" }}>Organization Member</div>
                    <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", lineHeight: 1.5 }}>
                      Collaborator with access to authorized projects, agents, and operational tools.
                    </p>
                  </div>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "14px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                    <div style={{ color: "#94a3b8", fontWeight: "700", marginBottom: "4px" }}>Organization Viewer</div>
                    <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", lineHeight: 1.5 }}>
                      Read-only auditing of dashboards, metrics, knowledge bases, and operational logs.
                    </p>
                  </div>
                </div>
              </div>

              {/* Security, Billing & Integrations */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">Security & SSO</h2>
                    <span className="badge badge-read">Configuration status</span>
                  </div>
                  <p className="data-note">Organization-level SSO, MFA policy, and billing settings are not exposed by the current backend API. Review the authenticated status on the <Link href="/security">Security page</Link>.</p>
                </div>

                <div className="card">
                  <div className="card-header">
                  <h2 className="card-title">Billing & quota</h2>
                  <span className="badge badge-read">Unavailable</span>
                  </div>
                  <p className="data-note">Plan, quota, and billing-contact data are not available from the current backend API.</p>
                </div>
              </div>

              {/* Organization Integrations */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <h2 className="card-title">Organization Integrations</h2>
                    <div className="card-subtitle">Platform-wide alert and monitoring webhooks</div>
                  </div>
                </div>
                <p className="data-note">Integration connections and webhook configuration are not exposed by the current backend API.</p>
              </div>
            </div>
          )}

          {/* TAB 2: PROJECT SETTINGS */}
          {activeTab === "project" && (
            <div style={{ display: "grid", gap: "24px" }}>
              {!activeProject ? (
                <div className="card" style={{ textAlign: "center", padding: "40px" }}>
                  <p style={{ color: "var(--muted)", margin: "0 0 16px 0" }}>
                    No project currently selected in <strong>{activeOrg?.name}</strong>.
                  </p>
                  <Link href="/projects" className="btn btn-primary">
                    Select or Create Project →
                  </Link>
                </div>
              ) : (
                <>
                  <div className="card">
                    <div className="card-header">
                      <div>
                        <h2 className="card-title">Project Profile: {activeProject.name}</h2>
                        <div className="card-subtitle">Project configuration and boundaries</div>
                      </div>
                      <span className="badge badge-write">PROJECT SCOPE</span>
                    </div>

                    <form onSubmit={handleSaveProject} style={{ display: "grid", gap: "16px", maxWidth: "600px" }}>
                      <div>
                        <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                          Project Name
                        </label>
                        <input
                          type="text"
                          value={projName}
                          onChange={(e) => { setProjSaved(false); setProjName(e.target.value); }}
                          disabled={!permissions.canManageProject()}
                          style={{
                            width: "100%",
                            padding: "10px 14px",
                            borderRadius: "8px",
                            background: "rgba(255, 255, 255, 0.05)",
                            border: "1px solid rgba(255, 255, 255, 0.12)",
                            color: "#ffffff",
                            fontSize: "13px",
                          }}
                        />
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                        <div>
                          <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                            Project Slug
                          </label>
                          <input
                            type="text"
                            value={activeProject.slug}
                            disabled
                            style={{
                              width: "100%",
                              padding: "10px 14px",
                              borderRadius: "8px",
                              background: "rgba(255, 255, 255, 0.02)",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              color: "#94a3b8",
                              fontFamily: "'DM Mono', monospace",
                              fontSize: "12px",
                            }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "6px" }}>
                            Parent Organization
                          </label>
                          <input
                            type="text"
                            value={activeOrg?.name || ""}
                            disabled
                            style={{
                              width: "100%",
                              padding: "10px 14px",
                              borderRadius: "8px",
                              background: "rgba(255, 255, 255, 0.02)",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              color: "#94a3b8",
                              fontSize: "12px",
                            }}
                          />
                        </div>
                      </div>

                      {permissions.canManageProject() && (
                        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "8px" }}>
                          <button
                            type="submit"
                            className="btn btn-primary"
                            style={{ padding: "8px 20px", fontSize: "13px" }}
                            disabled={savingSettings || !projName.trim()}
                          >
                                {savingSettings ? "Saving…" : "Save Project Changes"}
                          </button>
                          {projSaved && <span style={{ color: "#34d399", fontSize: "12px" }}>✓ Project updated</span>}
                        </div>
                      )}
                    </form>
                  </div>

                  {/* Project RBAC & Configuration */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
                    <div className="card">
                      <div className="card-header">
                        <h2 className="card-title">Project Roles & Members</h2>
                        <span className={`badge badge-${(activeProject.role || "read").toLowerCase()}`}>{activeProject.role || "Role not reported"}</span>
                      </div>
                      <div style={{ display: "grid", gap: "10px", fontSize: "12px" }}>
                        <div style={{ padding: "8px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "6px" }}>
                          <strong style={{ color: "#60a5fa" }}>Project Admin</strong>: Full control over project agents, RAG, and environments.
                        </div>
                        <div style={{ padding: "8px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "6px" }}>
                          <strong style={{ color: "#34d399" }}>Project Member</strong>: Can deploy and execute approved agent workflows.
                        </div>
                        <div style={{ padding: "8px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "6px" }}>
                          <strong style={{ color: "#94a3b8" }}>Project Viewer</strong>: Read-only visibility into project telemetry and runs.
                        </div>
                      </div>
                    </div>

                    <div className="card">
                      <div className="card-header">
                        <h2 className="card-title">Project Integrations & AI Gateway</h2>
                        <span className="badge badge-read">Not configured</span>
                      </div>
                      <p className="data-note">Repository, model gateway, and integration settings are not exposed by the current backend API.</p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 3: ENVIRONMENT SETTINGS */}
          {activeTab === "environment" && (
            <div style={{ display: "grid", gap: "24px" }}>
              {!activeEnvironment ? (
                <div className="card" style={{ textAlign: "center", padding: "40px" }}>
                  <p style={{ color: "var(--muted)", margin: "0 0 16px 0" }}>
                    No environment selected. Select or create an environment for <strong>{activeProject?.name || "your project"}</strong>.
                  </p>
                  <Link href="/projects" className="btn btn-primary">
                    Manage Environments →
                  </Link>
                </div>
              ) : (
                <>
                  <div className="card">
                    <div className="card-header">
                      <div>
                        <h2 className="card-title">Environment Configuration: {activeEnvironment.name}</h2>
                        <div className="card-subtitle">Environment-scoped operational configuration</div>
                      </div>
                      <span className="badge badge-admin" style={{ background: activeEnvironment.type === "Production" ? "#ef4444" : "#10b981", color: "#ffffff" }}>
                        {activeEnvironment.type.toUpperCase()}
                      </span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", fontSize: "12px", marginBottom: "20px" }}>
                      <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Environment Name</span>
                        <strong style={{ fontSize: "14px" }}>{activeEnvironment.name}</strong>
                      </div>
                      <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Environment Type</span>
                        <strong style={{ fontSize: "14px" }}>{activeEnvironment.type}</strong>
                      </div>
                      <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Kubernetes Namespace</span>
                        <span className="data-note">Not reported</span>
                      </div>
                      <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--muted)", display: "block" }}>Your Environment Role</span>
                        <strong style={{ color: "#34d399", fontSize: "14px" }}>
                          {activeEnvironment.role || "Not reported"}
                        </strong>
                      </div>
                    </div>

                    {/* Environment Roles Explanation */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px", fontSize: "11px" }}>
                      <div style={{ padding: "10px", background: "rgba(255, 255, 255, 0.02)", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                        <strong style={{ color: "#ef4444" }}>Environment Admin</strong>: Manage secrets, deployments, and access policies for this environment.
                      </div>
                      <div style={{ padding: "10px", background: "rgba(255, 255, 255, 0.02)", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                        <strong style={{ color: "#34d399" }}>Environment Operator</strong>: Deploy agent versions, view logs, and trigger operational playbooks.
                      </div>
                      <div style={{ padding: "10px", background: "rgba(255, 255, 255, 0.02)", borderRadius: "6px", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                        <strong style={{ color: "#94a3b8" }}>Environment Viewer</strong>: Read-only access to runtime metrics and incident logs.
                      </div>
                    </div>
                  </div>

                  <div className="card" id="secrets">
                    <div className="card-header">
                      <div>
                        <h2 className="card-title">Environment secrets</h2>
                        <div className="card-subtitle">Secret configuration is not managed by this application API.</div>
                      </div>
                    </div>
                    <p className="data-note">The API has no environment secret read/write endpoints. Connect a secret manager and add tenant-scoped, audited secret APIs before enabling this capability; no secrets are stored by this page.</p>
                  </div>

                  <div className="card">
                    <div className="card-header">
                      <h2 className="card-title">Runtime and deployment configuration</h2>
                      <span className="badge badge-read">Not reported</span>
                    </div>
                    <p className="data-note">Runtime quotas, replica policy, and deployment rollback settings are not exposed by the current backend API.</p>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 4: AUDIT LOGS */}
          {activeTab === "audit" && (
            <div className="card">
              <div className="card-header">
                <div>
                  <h2 className="card-title">Audit trail</h2>
                  <div className="card-subtitle">
                    Audit events available for <strong>{activeOrg?.name}</strong>.
                  </div>
                </div>
              </div>

              <div className="table-container">
                <table className="enterprise-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Action</th>
                      <th>Resource</th>
                      <th>Actor</th>
                      <th>Tenant Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditError && <tr><td colSpan={5} role="alert">{auditError}</td></tr>}
                    {loadingAudit ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                          Loading audit log records...
                        </td>
                      </tr>
                    ) : logs.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                          No audit events recorded yet for this tenant.
                        </td>
                      </tr>
                    ) : (
                      logs.map((log) => (
                        <tr key={log.id}>
                          <td style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: "var(--muted)" }}>
                            {new Date(log.created_at).toLocaleTimeString()} ({new Date(log.created_at).toLocaleDateString()})
                          </td>
                          <td>
                            <code style={{ fontSize: "11px", fontWeight: "700", color: "var(--forest)" }}>
                              {log.action}
                            </code>
                          </td>
                          <td>
                            <span style={{ fontSize: "11px" }}>
                              {log.resource_type}: <code>{log.resource_id}</code>
                            </span>
                          </td>
                          <td>
                            <span style={{ fontSize: "11px" }}>{log.actor_email || log.actor}</span>
                          </td>
                          <td>
                            <span className="badge badge-read" style={{ fontSize: "9px" }}>
                              {log.organization_id || "global"}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
