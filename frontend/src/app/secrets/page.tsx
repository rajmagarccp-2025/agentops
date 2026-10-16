"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "../../state/workspace-context";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";

interface SecretProvider {
  id: string;
  name: string;
  provider_type: string;
  endpoint_url?: string;
  vault_identifier?: string;
  region?: string;
  auth_method: string;
  status: string;
  last_validated_at?: string;
}

interface SecretAssignment {
  id: string;
  secret_id: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  assigned_by: string;
  assigned_at: string;
}

interface SecretMetadata {
  id: string;
  name: string;
  description: string;
  secret_type: string;
  provider_id: string;
  provider_type: string;
  provider_name: string;
  scope: string;
  tenant_id: string;
  project_id?: string;
  environment_id?: string;
  current_version_num: number;
  created_by: string;
  modified_by: string;
  created_at: string;
  updated_at: string;
  status: string;
  expiration_date?: string;
  rotation_interval_days?: number;
  last_rotated_at?: string;
  metadata: Record<string, unknown>;
  assigned_entities: SecretAssignment[];
}

interface SecretAuditEvent {
  id: string;
  actor: string;
  actor_email?: string | null;
  action: string;
  resource_id: string;
  created_at: string;
  details?: Record<string, unknown> | null;
}

function getResponseErrorMessage(payload: unknown): string | null {
  if (typeof payload !== "object" || payload === null) return null;
  const body = payload as Record<string, unknown>;
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.error === "string") return body.error;
  return null;
}

async function ensureResponseOk(response: Response, fallback: string): Promise<void> {
  if (response.ok) return;
  const payload: unknown = await response.json().catch(() => null);
  throw new Error(getResponseErrorMessage(payload) || `${fallback} (${response.status}).`);
}

export default function SecretsPage() {
  const { activeOrg, activeProject, activeEnvironment, effectiveRole, user, permissions } = useWorkspace();
  const canReadSecrets = permissions.hasPermission("secrets:read");
  const [activeTab, setActiveTab] = useState<"overview" | "providers" | "assignments" | "audit">("overview");

  const [secrets, setSecrets] = useState<SecretMetadata[]>([]);
  const [providers, setProviders] = useState<SecretProvider[]>([]);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadCount, setReloadCount] = useState(0);
  const [auditEvents, setAuditEvents] = useState<SecretAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditReloadCount, setAuditReloadCount] = useState(0);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedScope, setSelectedScope] = useState<string>("all");

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRevealModal, setShowRevealModal] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<{ name: string; value: string; version: number } | null>(null);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [targetSecretForAssign, setTargetSecretForAssign] = useState<SecretMetadata | null>(null);

  // Form states
  const [newSecret, setNewSecret] = useState({
    name: "",
    description: "",
    secret_type: "api_key",
    provider_id: "",
    scope: "environment",
    value: "",
    rotation_interval_days: 90,
  });

  const [newAssign, setNewAssign] = useState({
    entity_type: "agent",
    entity_id: "",
    entity_name: "",
  });

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setLoadError(null);
    setSecrets([]);
    setProviders([]);
    if (!canReadSecrets || !activeOrg?.id || !activeProject?.id || !activeEnvironment?.id) {
      setIsLoading(false);
      return () => controller.abort();
    }

    const fetchData = async () => {
      try {
        const [secRes, provRes] = await Promise.all([
          fetch("/api/proxy/secrets", { signal: controller.signal }),
          fetch("/api/proxy/secret-providers", { signal: controller.signal }),
        ]);
        await ensureResponseOk(secRes, "Unable to load secrets");
        await ensureResponseOk(provRes, "Unable to load secret providers");
        const [secretData, providerData] = await Promise.all([secRes.json(), provRes.json()]);
        if (!Array.isArray(secretData) || !Array.isArray(providerData)) {
          throw new Error("The secrets service returned an invalid response.");
        }
        setSecrets(secretData);
        setProviders(providerData);
        setNewSecret((prev) => ({
          ...prev,
          provider_id: providerData[0]?.id || "",
        }));
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        setSecrets([]);
        setProviders([]);
        setLoadError(err instanceof Error ? err.message : "Unable to load secrets and providers.");
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };

    void fetchData();
    return () => controller.abort();
  }, [activeOrg?.id, activeProject?.id, activeEnvironment?.id, canReadSecrets, reloadCount]);

  const canReadAudit = permissions.hasPermission("secrets:audit:read");
  const canCreateSecrets = permissions.hasPermission("secrets:create");
  const canRevealSecrets = permissions.hasPermission("secrets:value:read");
  const canRotateSecrets = permissions.hasPermission("secrets:rotate");
  const canAssignSecrets = permissions.hasPermission("secrets:assign");
  const canRevokeAssignments = permissions.hasPermission("secrets:unassign");
  const canDeleteSecrets = permissions.hasPermission("secrets:delete");

  useEffect(() => {
    if (activeTab !== "audit" || !canReadAudit) return;
    const controller = new AbortController();
    setAuditLoading(true);
    setAuditError(null);
    setAuditEvents([]);

    const fetchAudit = async () => {
      try {
        const responses = await Promise.all(secrets.map((secret) =>
          fetch(`/api/proxy/secrets/${secret.id}/audit`, { signal: controller.signal }),
        ));
        for (const response of responses) {
          await ensureResponseOk(response, "Unable to load secret audit events");
        }
        const eventGroups = await Promise.all(
          responses.map((response) => response.json() as Promise<SecretAuditEvent[]>),
        );
        setAuditEvents(eventGroups.flat().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)));
      } catch (err: unknown) {
        if (!controller.signal.aborted) {
          setAuditError(err instanceof Error ? err.message : "Unable to load secret audit events.");
          setAuditEvents([]);
        }
      } finally {
        if (!controller.signal.aborted) setAuditLoading(false);
      }
    };

    void fetchAudit();
    return () => controller.abort();
  }, [activeTab, auditReloadCount, canReadAudit, secrets]);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const handleCreateSecret = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSecret.name || !newSecret.value) {
      setErrorMessage("Secret name and value are required.");
      return;
    }
    if (!canCreateSecrets) {
      setErrorMessage("Your role does not have permission to create secrets.");
      return;
    }

    try {
      const res = await fetch("/api/proxy/secrets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSecret),
      });
      await ensureResponseOk(res, "Unable to create secret");
      const created = await res.json() as SecretMetadata;
      setSecrets((prev) => [created, ...prev]);
      showToast(`🔐 Secret "${created.name}" securely created!`);
      setShowCreateModal(false);
      setNewSecret({
        name: "",
        description: "",
        secret_type: "api_key",
        provider_id: providers[0]?.id || "",
        scope: "environment",
        value: "",
        rotation_interval_days: 90,
      });
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to create secret.");
    }
  };

  const handleRevealSecret = async (secret: SecretMetadata) => {
    if (!canRevealSecrets) {
      setErrorMessage("Your role does not have permission to reveal secret values.");
      return;
    }

    try {
      const res = await fetch(`/api/proxy/secrets/${secret.id}/reveal`, { method: "POST" });
      await ensureResponseOk(res, "Unable to reveal secret");
      const data = await res.json();
      setRevealedSecret({ name: secret.name, value: data.value, version: data.version_num });
      setShowRevealModal(true);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to reveal secret.");
    }
  };

  const handleRotateSecret = async (secret: SecretMetadata) => {
    if (!canRotateSecrets) {
      setErrorMessage("Your role does not have permission to rotate secrets.");
      return;
    }
    try {
      const res = await fetch(`/api/proxy/secrets/${secret.id}/rotate`, { method: "POST" });
      await ensureResponseOk(res, "Unable to rotate secret");
      const updated = await res.json() as SecretMetadata;
      setSecrets((prev) => prev.map((s) => (s.id === secret.id ? updated : s)));
      showToast(`⚡ Secret "${secret.name}" successfully rotated to Version ${updated.current_version_num}!`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to rotate secret.");
    }
  };

  const handleTestProvider = async (provider: SecretProvider) => {
    try {
      const res = await fetch(`/api/proxy/secret-providers/${provider.id}/test`, { method: "POST" });
      await ensureResponseOk(res, `Unable to test provider "${provider.name}"`);
      const data = await res.json();
      showToast(`✅ Provider "${provider.name}" tested: ${data.message}`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : `Unable to test provider "${provider.name}".`);
    }
  };

  const handleAssignEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetSecretForAssign || !newAssign.entity_id || !newAssign.entity_name) return;
    if (!canAssignSecrets) {
      setErrorMessage("Your role does not have permission to assign secrets.");
      return;
    }

    try {
      const res = await fetch(`/api/proxy/secrets/${targetSecretForAssign.id}/assignments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newAssign),
      });
      await ensureResponseOk(res, "Unable to assign secret");
      const assignment = await res.json() as SecretAssignment;
      setSecrets((prev) =>
        prev.map((s) =>
          s.id === targetSecretForAssign.id
            ? { ...s, assigned_entities: [...s.assigned_entities, assignment] }
            : s
        )
      );
      showToast(`🔗 Assigned "${newAssign.entity_name}" to secret "${targetSecretForAssign.name}"!`);
      setShowAssignModal(false);
      setNewAssign({ entity_type: "agent", entity_id: "", entity_name: "" });
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to assign secret.");
    }
  };

  const handleRevokeAssignment = async (secretId: string, assignmentId: string, entityName: string) => {
    if (!canRevokeAssignments) {
      setErrorMessage("Your role does not have permission to revoke secret assignments.");
      return;
    }
    try {
      const response = await fetch(`/api/proxy/secrets/${secretId}/assignments/${assignmentId}`, { method: "DELETE" });
      await ensureResponseOk(response, "Unable to revoke secret assignment");
      setSecrets((prev) =>
        prev.map((s) =>
          s.id === secretId
            ? { ...s, assigned_entities: s.assigned_entities.filter((a) => a.id !== assignmentId) }
            : s
        )
      );
      showToast(`🗑️ Revoked access for "${entityName}"!`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to revoke secret assignment.");
    }
  };

  const handleDeleteSecret = async (secret: SecretMetadata) => {
    if (!canDeleteSecrets) {
      setErrorMessage("Your role does not have permission to delete secrets.");
      return;
    }

    if (!confirm(`Are you sure you want to permanently delete secret "${secret.name}"?`)) return;

    try {
      const response = await fetch(`/api/proxy/secrets/${secret.id}`, { method: "DELETE" });
      await ensureResponseOk(response, "Unable to delete secret");
      setSecrets((prev) => prev.filter((s) => s.id !== secret.id));
      showToast(`🗑️ Secret "${secret.name}" deleted.`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Unable to delete secret.");
    }
  };

  // Filtered Secrets
  const filteredSecrets = secrets.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = selectedType === "all" || s.secret_type === selectedType;
    const matchesScope = selectedScope === "all" || s.scope === selectedScope;
    return matchesSearch && matchesType && matchesScope;
  });

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">Workspace <strong>/ {activeOrg?.name || "Organization"} / Secrets</strong></span>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Secrets management" permission="secrets:read">
            <GlobalContextSelector />
            <div style={{ maxWidth: "1400px", margin: "0 auto", color: "#f8fafc" }}>
              {errorMessage && (
                <section className="panel error-panel" role="alert">
                  <p>{errorMessage}</p>
                  <button type="button" className="btn btn-secondary" onClick={() => setErrorMessage(null)}>Dismiss</button>
                </section>
              )}
              {loadError && (
                <section className="panel error-panel" role="alert">
                  <p>{loadError}</p>
                  <button type="button" className="btn btn-secondary" onClick={() => setReloadCount((count) => count + 1)}>
                    Retry loading secrets
                  </button>
                </section>
              )}
              {isLoading && <p className="data-note" role="status">Loading secrets and vault providers…</p>}
              {!isLoading && !loadError && (
                <>
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            top: "20px",
            right: "20px",
            zIndex: 9999,
            background: "#0f172a",
            border: "1px solid #3b82f6",
            boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
            borderRadius: "8px",
            padding: "14px 20px",
            color: "#60a5fa",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* Header Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
          padding: "20px 28px",
          borderRadius: "12px",
          border: "1px solid #334155",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 style={{ margin: 0, fontSize: "24px", fontWeight: 700, color: "#f8fafc" }}>
              Enterprise Secrets Management & Vault Integrations
            </h1>
            <span
              style={{
                background: "rgba(16, 185, 129, 0.15)",
                border: "1px solid rgba(16, 185, 129, 0.4)",
                color: "#34d399",
                fontSize: "11px",
                fontWeight: 700,
                padding: "3px 9px",
                borderRadius: "20px",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Service-backed secret catalog
            </span>
          </div>
          <p style={{ margin: "6px 0 0", color: "#94a3b8", fontSize: "13px" }}>
            Hierarchical secret scopes, external KMS/Vault adapters, RBAC enforcement, & runtime secret injection.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          disabled={!canCreateSecrets || providers.length === 0}
          style={{
            background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            padding: "10px 20px",
            fontWeight: 600,
            fontSize: "13px",
            cursor: canCreateSecrets && providers.length > 0 ? "pointer" : "not-allowed",
            opacity: canCreateSecrets && providers.length > 0 ? 1 : 0.5,
            boxShadow: "0 4px 12px rgba(37, 99, 235, 0.3)",
          }}
        >
          + Create Secret
        </button>
      </div>

      {/* KPI Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Total Secrets</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#38bdf8", marginTop: "4px" }}>{secrets.length}</div>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>Active across Org, Project & Envs</div>
        </div>

        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Vault Providers</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#34d399", marginTop: "4px" }}>{providers.length}</div>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>Configured for this workspace</div>
        </div>

        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Entity Assignments</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#a78bfa", marginTop: "4px" }}>
            {secrets.reduce((acc, s) => acc + s.assigned_entities.length, 0)}
          </div>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>AI Agents, Services & Pipelines</div>
        </div>

        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "16px 20px" }}>
          <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Active Role</div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "#f59e0b", marginTop: "6px" }}>{effectiveRole}</div>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
            {canDeleteSecrets ? "Secret administration permitted" : "Scoped secret access"}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #334155", marginBottom: "20px" }}>
        {[
          { key: "overview" as const, label: "🔑 Secrets Overview" },
          { key: "providers" as const, label: "🔌 Vault Providers" },
          { key: "assignments" as const, label: "👥 Entity Assignments" },
          ...(canReadAudit ? [{ key: "audit" as const, label: "📜 Audit Trail" }] : []),
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: activeTab === tab.key ? "#1e293b" : "transparent",
              color: activeTab === tab.key ? "#38bdf8" : "#94a3b8",
              border: "none",
              borderBottom: activeTab === tab.key ? "2px solid #38bdf8" : "2px solid transparent",
              padding: "10px 18px",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div>
          {/* Controls Bar */}
          <div style={{ display: "flex", gap: "12px", marginBottom: "16px", flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Search secret name or description..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                flex: 1,
                minWidth: "240px",
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "8px 12px",
                color: "#f8fafc",
                fontSize: "13px",
              }}
            />

            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "8px 12px",
                color: "#f8fafc",
                fontSize: "13px",
              }}
            >
              <option value="all">All Secret Types</option>
              <option value="api_key">LLM & API Keys</option>
              <option value="database_credential">Database Credentials</option>
              <option value="cloud_credential">Cloud IAM Credentials</option>
              <option value="oauth_secret">OAuth & Webhook Secrets</option>
              <option value="password">Passwords</option>
            </select>

            <select
              value={selectedScope}
              onChange={(e) => setSelectedScope(e.target.value)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "8px 12px",
                color: "#f8fafc",
                fontSize: "13px",
              }}
            >
              <option value="all">All Scopes</option>
              <option value="organization">Organization Scope</option>
              <option value="project">Project Scope</option>
              <option value="environment">Environment Scope</option>
            </select>
          </div>

          {/* Secrets Table */}
          <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "13px" }}>
              <thead>
                <tr style={{ background: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
                  <th style={{ padding: "12px 16px" }}>Secret Name</th>
                  <th style={{ padding: "12px 16px" }}>Type</th>
                  <th style={{ padding: "12px 16px" }}>Scope</th>
                  <th style={{ padding: "12px 16px" }}>Provider</th>
                  <th style={{ padding: "12px 16px" }}>Ver</th>
                  <th style={{ padding: "12px 16px" }}>Assigned Entities</th>
                  <th style={{ padding: "12px 16px" }}>Status</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSecrets.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: "32px", textAlign: "center", color: "#64748b" }}>
                      No secrets found matching filters.
                    </td>
                  </tr>
                ) : (
                  filteredSecrets.map((s) => (
                    <tr key={s.id} style={{ borderBottom: "1px solid #334155" }}>
                      <td style={{ padding: "14px 16px" }}>
                        <div style={{ fontWeight: 600, color: "#f8fafc" }}>{s.name}</div>
                        <div style={{ fontSize: "11px", color: "#94a3b8" }}>{s.description || "No description"}</div>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span
                          style={{
                            background: "rgba(56, 189, 248, 0.1)",
                            color: "#38bdf8",
                            border: "1px solid rgba(56, 189, 248, 0.3)",
                            fontSize: "11px",
                            padding: "2px 8px",
                            borderRadius: "4px",
                          }}
                        >
                          {s.secret_type}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span
                          style={{
                            background:
                              s.scope === "organization"
                                ? "rgba(168, 85, 247, 0.15)"
                                : s.scope === "project"
                                ? "rgba(59, 130, 246, 0.15)"
                                : "rgba(16, 185, 129, 0.15)",
                            color:
                              s.scope === "organization"
                                ? "#c084fc"
                                : s.scope === "project"
                                ? "#60a5fa"
                                : "#34d399",
                            fontSize: "11px",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            textTransform: "capitalize",
                          }}
                        >
                          {s.scope}
                        </span>
                      </td>
                      <td style={{ padding: "14px 16px", color: "#cbd5e1" }}>{s.provider_name}</td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{ fontWeight: 600, color: "#f59e0b" }}>v{s.current_version_num}</span>
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        {s.assigned_entities.length === 0 ? (
                          <span style={{ color: "#64748b", fontSize: "11px" }}>None</span>
                        ) : (
                          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                            {s.assigned_entities.map((a) => (
                              <span
                                key={a.id}
                                style={{
                                  background: "#0f172a",
                                  border: "1px solid #334155",
                                  color: "#94a3b8",
                                  fontSize: "10px",
                                  padding: "2px 6px",
                                  borderRadius: "4px",
                                }}
                              >
                                {a.entity_name}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "14px 16px" }}>
                        <span style={{ color: "#34d399", fontWeight: 600, fontSize: "12px" }}>● {s.status}</span>
                      </td>
                      <td style={{ padding: "14px 16px", textAlign: "right" }}>
                        <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                          <button
                            onClick={() => handleRevealSecret(s)}
                            disabled={!canRevealSecrets}
                            style={{
                              background: "#0f172a",
                              border: "1px solid #3b82f6",
                              color: "#60a5fa",
                              borderRadius: "4px",
                              padding: "4px 8px",
                              fontSize: "11px",
                              cursor: "pointer",
                            }}
                            title="Reveal Secret Value"
                          >
                            👁 Reveal
                          </button>

                          <button
                            onClick={() => handleRotateSecret(s)}
                            disabled={!canRotateSecrets}
                            style={{
                              background: "#0f172a",
                              border: "1px solid #f59e0b",
                              color: "#fbbf24",
                              borderRadius: "4px",
                              padding: "4px 8px",
                              fontSize: "11px",
                              cursor: "pointer",
                            }}
                            title="Rotate Secret"
                          >
                            ⚡ Rotate
                          </button>

                          <button
                            onClick={() => {
                              setTargetSecretForAssign(s);
                              setShowAssignModal(true);
                            }}
                            disabled={!canAssignSecrets}
                            style={{
                              background: "#0f172a",
                              border: "1px solid #8b5cf6",
                              color: "#c084fc",
                              borderRadius: "4px",
                              padding: "4px 8px",
                              fontSize: "11px",
                              cursor: "pointer",
                            }}
                            title="Assign to Agent/Service"
                          >
                            🔗 Assign
                          </button>

                          <button
                            onClick={() => handleDeleteSecret(s)}
                            disabled={!canDeleteSecrets}
                            style={{
                              background: "#0f172a",
                              border: "1px solid #ef4444",
                              color: "#f87171",
                              borderRadius: "4px",
                              padding: "4px 8px",
                              fontSize: "11px",
                              cursor: canDeleteSecrets ? "pointer" : "not-allowed",
                              opacity: canDeleteSecrets ? 1 : 0.4,
                            }}
                            title="Delete Secret"
                          >
                            🗑
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: PROVIDERS */}
      {activeTab === "providers" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
          {providers.map((p) => (
            <div
              key={p.id}
              style={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "10px",
                padding: "20px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <h3 style={{ margin: 0, fontSize: "16px", color: "#f8fafc" }}>{p.name}</h3>
                  <span
                    style={{
                      background: p.status === "connected" ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
                      color: p.status === "connected" ? "#34d399" : "#fbbf24",
                      fontSize: "11px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "4px",
                    }}
                  >
                    ● {p.status}
                  </span>
                </div>

                <div style={{ marginTop: "12px", fontSize: "12px", color: "#94a3b8" }}>
                  <div><strong>Type:</strong> {p.provider_type}</div>
                  <div><strong>Auth Method:</strong> {p.auth_method}</div>
                  {p.vault_identifier && <div><strong>Vault / Identifier:</strong> {p.vault_identifier}</div>}
                  {p.region && <div><strong>Region:</strong> {p.region}</div>}
                  {p.endpoint_url && <div><strong>Endpoint:</strong> {p.endpoint_url}</div>}
                </div>
              </div>

              <div style={{ marginTop: "20px", paddingTop: "14px", borderTop: "1px solid #334155", display: "flex", gap: "8px" }}>
                <button
                  onClick={() => handleTestProvider(p)}
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    border: "1px solid #3b82f6",
                    color: "#60a5fa",
                    padding: "8px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Test Connection
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: ASSIGNMENTS */}
      {activeTab === "assignments" && (
        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "20px" }}>
          <h3 style={{ marginTop: 0, color: "#f8fafc", fontSize: "16px" }}>Entity Secret Mappings</h3>
          <p style={{ color: "#94a3b8", fontSize: "13px" }}>
            Many-to-Many runtime authorization linking AI Agents, Services, Applications, & Workflows to scoped secrets.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "16px", fontSize: "13px" }}>
            <thead>
              <tr style={{ background: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
                <th style={{ padding: "10px 14px" }}>Secret</th>
                <th style={{ padding: "10px 14px" }}>Entity Type</th>
                <th style={{ padding: "10px 14px" }}>Entity Name</th>
                <th style={{ padding: "10px 14px" }}>Entity ID</th>
                <th style={{ padding: "10px 14px" }}>Assigned By</th>
                <th style={{ padding: "10px 14px", textAlign: "right" }}>Revoke</th>
              </tr>
            </thead>
            <tbody>
              {secrets.flatMap((s) =>
                s.assigned_entities.map((a) => (
                  <tr key={a.id} style={{ borderBottom: "1px solid #334155" }}>
                    <td style={{ padding: "12px 14px", fontWeight: 600, color: "#38bdf8" }}>{s.name}</td>
                    <td style={{ padding: "12px 14px", textTransform: "capitalize", color: "#cbd5e1" }}>{a.entity_type}</td>
                    <td style={{ padding: "12px 14px", fontWeight: 600, color: "#f8fafc" }}>{a.entity_name}</td>
                    <td style={{ padding: "12px 14px", fontFamily: "monospace", color: "#94a3b8", fontSize: "11px" }}>{a.entity_id}</td>
                    <td style={{ padding: "12px 14px", color: "#94a3b8" }}>{a.assigned_by}</td>
                    <td style={{ padding: "12px 14px", textAlign: "right" }}>
                      <button
                        onClick={() => handleRevokeAssignment(s.id, a.id, a.entity_name)}
                        style={{
                          background: "#0f172a",
                          border: "1px solid #ef4444",
                          color: "#f87171",
                          borderRadius: "4px",
                          padding: "4px 8px",
                          fontSize: "11px",
                          cursor: "pointer",
                        }}
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 4: AUDIT */}
      {activeTab === "audit" && canReadAudit && (
        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "10px", padding: "20px" }}>
          <h3 style={{ marginTop: 0, color: "#f8fafc", fontSize: "16px" }}>Security & Governance Audit Trail</h3>
          <p style={{ color: "#94a3b8", fontSize: "13px" }}>
            Immutable security log of all secret access, creation, rotations, value reveals, and entity assignments.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "16px", fontSize: "12px" }}>
            <thead>
              <tr style={{ background: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
                <th style={{ padding: "10px" }}>Timestamp</th>
                <th style={{ padding: "10px" }}>Actor</th>
                <th style={{ padding: "10px" }}>Action</th>
                <th style={{ padding: "10px" }}>Target Secret ID</th>
                <th style={{ padding: "10px" }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {auditLoading && <tr><td colSpan={5} role="status" style={{ padding: "18px", color: "#94a3b8" }}>Loading audit events…</td></tr>}
              {auditError && (
                <tr>
                  <td colSpan={5} style={{ padding: "18px" }}>
                    <div className="error-panel" role="alert">{auditError}</div>
                    <button type="button" className="secondary-button" onClick={() => setAuditReloadCount((count) => count + 1)}>Retry</button>
                  </td>
                </tr>
              )}
              {!auditLoading && !auditError && auditEvents.length === 0 && (
                <tr><td colSpan={5} style={{ padding: "18px", color: "#94a3b8" }}>No secret audit events are recorded.</td></tr>
              )}
              {!auditError && auditEvents.map((event) => (
                <tr key={event.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "10px", color: "#94a3b8" }}>{new Date(event.created_at).toLocaleString()}</td>
                  <td style={{ padding: "10px", color: "#f8fafc", fontWeight: 500 }}>{event.actor_email || event.actor}</td>
                  <td style={{ padding: "10px" }}>
                    <span style={{ color: "#38bdf8", fontWeight: 600 }}>{event.action}</span>
                  </td>
                  <td style={{ padding: "10px", fontFamily: "monospace", color: "#cbd5e1" }}>{event.resource_id}</td>
                  <td style={{ padding: "10px", color: "#94a3b8" }}>{event.details ? JSON.stringify(event.details) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* MODAL: CREATE SECRET */}
      {showCreateModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "12px", padding: "24px", width: "100%", maxWidth: "560px", color: "#f8fafc" }}>
            <h3 style={{ marginTop: 0, fontSize: "18px" }}>Create New Secret</h3>
            <form onSubmit={handleCreateSecret} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Secret Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. OPENAI_API_KEY"
                  value={newSecret.name}
                  onChange={(e) => setNewSecret({ ...newSecret, name: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Description</label>
                <input
                  type="text"
                  placeholder="Usage description..."
                  value={newSecret.description}
                  onChange={(e) => setNewSecret({ ...newSecret, description: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Secret Type</label>
                  <select
                    value={newSecret.secret_type}
                    onChange={(e) => setNewSecret({ ...newSecret, secret_type: e.target.value })}
                    style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                  >
                    <option value="api_key">API Key</option>
                    <option value="database_credential">Database Credential</option>
                    <option value="cloud_credential">Cloud Credential</option>
                    <option value="oauth_secret">OAuth / Signing Secret</option>
                    <option value="password">Password</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Provider Vault</label>
                  <select
                    value={newSecret.provider_id}
                    onChange={(e) => setNewSecret({ ...newSecret, provider_id: e.target.value })}
                    style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                  >
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Hierarchical Scope</label>
                <select
                  value={newSecret.scope}
                  onChange={(e) => setNewSecret({ ...newSecret, scope: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                >
                  <option value="organization">Organization Scope (Shared across Organization)</option>
                  <option value="project">Project Scope (Restricted to Project)</option>
                  <option value="environment">Environment Scope (Restricted to Environment)</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Secret Value * (Write-Only)</label>
                <input
                  type="password"
                  required
                  placeholder="Paste secret value..."
                  value={newSecret.value}
                  onChange={(e) => setNewSecret({ ...newSecret, value: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                />
              </div>

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ background: "#0f172a", border: "1px solid #334155", color: "#94a3b8", borderRadius: "6px", padding: "8px 16px", cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ background: "#2563eb", color: "#fff", border: "none", borderRadius: "6px", padding: "8px 16px", fontWeight: 600, cursor: "pointer" }}
                >
                  Save Secret
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: REVEAL SECRET VALUE */}
      {showRevealModal && revealedSecret && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#1e293b", border: "1px solid #3b82f6", borderRadius: "12px", padding: "24px", width: "100%", maxWidth: "480px", color: "#f8fafc" }}>
            <h3 style={{ marginTop: 0, fontSize: "16px", color: "#60a5fa" }}>👁 Secret Value Revealed (Audited)</h3>
            <p style={{ fontSize: "12px", color: "#94a3b8" }}>
              This operation has been logged in the security audit trail with actor <strong>{user?.email || "you"}</strong>.
            </p>

            <div style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "12px", margin: "16px 0", fontFamily: "monospace", fontSize: "13px", wordBreak: "break-all", color: "#34d399" }}>
              {revealedSecret.value}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  setShowRevealModal(false);
                  setRevealedSecret(null);
                }}
                style={{ background: "#3b82f6", color: "#fff", border: "none", borderRadius: "6px", padding: "8px 16px", fontWeight: 600, cursor: "pointer" }}
              >
                Close & Mask
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: ASSIGN ENTITY */}
      {showAssignModal && targetSecretForAssign && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "12px", padding: "24px", width: "100%", maxWidth: "480px", color: "#f8fafc" }}>
            <h3 style={{ marginTop: 0, fontSize: "16px" }}>Assign Secret &quot;{targetSecretForAssign.name}&quot;</h3>
            <form onSubmit={handleAssignEntity} style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Entity Type</label>
                <select
                  value={newAssign.entity_type}
                  onChange={(e) => setNewAssign({ ...newAssign, entity_type: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                >
                  <option value="agent">AI Agent</option>
                  <option value="service">Service Core</option>
                  <option value="application">Application</option>
                  <option value="model_deployment">Model Deployment</option>
                  <option value="workflow">Workflow / Pipeline</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Entity Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. SRE Remediation Autopilot"
                  value={newAssign.entity_name}
                  onChange={(e) => setNewAssign({ ...newAssign, entity_name: e.target.value, entity_id: e.target.value.toLowerCase().replace(/\s+/g, "-") })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "4px" }}>Entity Identifier *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. sre-agent-01"
                  value={newAssign.entity_id}
                  onChange={(e) => setNewAssign({ ...newAssign, entity_id: e.target.value })}
                  style={{ width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: "6px", padding: "8px 12px", color: "#f8fafc", fontSize: "13px" }}
                />
              </div>

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setShowAssignModal(false)}
                  style={{ background: "#0f172a", border: "1px solid #334155", color: "#94a3b8", borderRadius: "6px", padding: "8px 16px", cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ background: "#8b5cf6", color: "#fff", border: "none", borderRadius: "6px", padding: "8px 16px", fontWeight: 600, cursor: "pointer" }}
                >
                  Assign Access
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
                </>
              )}
            </div>
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
