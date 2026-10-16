"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Navigation } from "../../components/navigation";
import { useWorkspace } from "../../state/workspace-context";
import { createPermissionEngine } from "../../lib/permissions";
import { GlobalContextSelector } from "../../components/global-context-selector";

interface EnvironmentItem {
  id: string;
  name: string;
  type: string;
  slug: string;
  can_delete?: boolean;
  description?: string | null;
  status?: string;
  created_at?: string;
}

interface ProjectItem {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  environments?: EnvironmentItem[];
  role?: string;
  created_at?: string;
}

export default function ProjectsPage() {
  const { currentOrg, effectiveRole, refreshWorkspace, permissions } = useWorkspace();
  const [projectList, setProjectList] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showEnvModal, setShowEnvModal] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [pendingDeleteEnvironment, setPendingDeleteEnvironment] = useState<EnvironmentItem | null>(null);
  const [productionConfirmation, setProductionConfirmation] = useState("");

  // New Project Form state
  const [projName, setProjName] = useState("");
  const [projSlug, setProjSlug] = useState("");
  const [projDesc, setProjDesc] = useState("");
  const [initialEnvName, setInitialEnvName] = useState("Production");
  const [initialEnvType, setInitialEnvType] = useState("Production");

  // New Environment Form state
  const [envName, setEnvName] = useState("");
  const [envType, setEnvType] = useState("Development");
  const [envDesc, setEnvDesc] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const canCreateProject = permissions.canManageProject();
  const fetchProjectsAndEnvs = useCallback(async () => {
    if (!currentOrg?.id) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/proxy/organizations/${currentOrg.id}/projects`);
      if (!res.ok) {
        throw new Error(`Unable to load projects (${res.status}).`);
      }
      const projs: ProjectItem[] = await res.json();
      const fullProjs = await Promise.all(
        projs.map(async (project) => {
          const envRes = await fetch(`/api/proxy/projects/${project.id}/environments`);
          if (!envRes.ok) {
            throw new Error(`Unable to load environments for ${project.name} (${envRes.status}).`);
          }
          return { ...project, environments: await envRes.json() };
        }),
      );
      setProjectList(fullProjs);
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Unable to load projects.",
      });
    } finally {
      setLoading(false);
    }
  }, [currentOrg?.id]);

  useEffect(() => {
    setFeedback(null);
    void fetchProjectsAndEnvs();
  }, [fetchProjectsAndEnvs]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg?.id || !projName.trim()) return;
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch(`/api/proxy/organizations/${currentOrg.id}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projName.trim(),
          slug: projSlug.trim() || undefined,
          description: projDesc.trim() || undefined,
          initial_environment_name: initialEnvName.trim() || undefined,
          initial_environment_type: initialEnvType || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create project");
      }

      setFeedback({ type: "success", message: `Project ${projName} created successfully!` });
      setShowProjectModal(false);
      setProjName("");
      setProjSlug("");
      setProjDesc("");
      await fetchProjectsAndEnvs();
      await refreshWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Creation failed";
      setFeedback({ type: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateEnvironment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProjectId || !envName.trim()) return;
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch(`/api/proxy/projects/${selectedProjectId}/environments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: envName.trim(),
          type: envType,
          description: envDesc.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create environment");
      }

      setFeedback({ type: "success", message: `Environment ${envName} added successfully!` });
      setShowEnvModal(false);
      setEnvName("");
      setEnvDesc("");
      await fetchProjectsAndEnvs();
      await refreshWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Creation failed";
      setFeedback({ type: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteEnvironment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingDeleteEnvironment) return;
    if (
      pendingDeleteEnvironment.type === "Production"
      && productionConfirmation !== pendingDeleteEnvironment.slug
    ) {
      setFeedback({ type: "error", message: "Enter the exact environment slug to confirm Production deletion." });
      return;
    }
    setSubmitting(true);
    setFeedback(null);
    try {
      const headers = new Headers();
      if (pendingDeleteEnvironment.type === "Production") {
        headers.set("X-Confirm-Production-Environment", productionConfirmation);
      }
      const response = await fetch(`/api/proxy/environments/${encodeURIComponent(pendingDeleteEnvironment.id)}`, {
        method: "DELETE",
        headers,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(typeof payload?.detail === "string" ? payload.detail : `Unable to delete environment (${response.status}).`);
      }
      setFeedback({ type: "success", message: `${pendingDeleteEnvironment.name} was deleted.` });
      setPendingDeleteEnvironment(null);
      setProductionConfirmation("");
      await fetchProjectsAndEnvs();
      await refreshWorkspace();
    } catch (err: unknown) {
      setFeedback({ type: "error", message: err instanceof Error ? err.message : "Unable to delete environment." });
    } finally {
      setSubmitting(false);
    }
  };

  // Rule 6 enforcement: Must have organization
  if (!currentOrg) {
    return (
      <div className="shell">
        <Navigation />
        <div className="main">
          <main className="main-content" style={{ textAlign: "center", paddingTop: "80px" }}>
            <div className="card" style={{ maxWidth: "520px", margin: "0 auto", padding: "40px" }}>
              <div style={{ fontSize: "36px", marginBottom: "16px" }}>🏢</div>
              <h2 style={{ fontSize: "20px", marginBottom: "12px" }}>
                You need an organization before creating a project.
              </h2>
              <p style={{ fontSize: "13px", color: "var(--muted)", lineHeight: 1.6, marginBottom: "24px" }}>
                Projects cannot exist independently. They must belong strictly to an authorized organization tenant.
              </p>
              <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
                <Link href="/onboarding" className="btn btn-primary">
                  Create Organization
                </Link>
                <Link href="/onboarding" className="btn btn-secondary">
                  Join Organization
                </Link>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">
              Workspace <strong>/ {currentOrg?.name}</strong> / Projects
            </span>
          </div>
          <div className="topbar-actions">
            <span className={`badge badge-${effectiveRole.toLowerCase()}`}>
              Your Role: {effectiveRole}
            </span>
          </div>
        </header>

        <main className="main-content">
          <GlobalContextSelector />
          <section className="page-heading">
            <div>
              <span className="kicker">Tenant Hierarchy: Organization → Project → Environment</span>
              <h1>Projects & Environments</h1>
              <p className="lede">
                Isolated operational boundaries within <strong>{currentOrg?.name}</strong>.
              </p>
              <p className="hierarchy-explainer">
                Projects contain environments. Applications are workloads shown in Infrastructure resources,
                not a separate hierarchy level; Agents are operational workflows scoped to the selected project
                and environment.
              </p>
            </div>

            {canCreateProject && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowProjectModal(true)}
              >
                + Create Project
              </button>
            )}
          </section>

          {feedback && (
            <div className={`alert-banner ${feedback.type}`} style={{ marginBottom: "20px" }}>
              <span>{feedback.type === "success" ? "✓" : "⚠️"}</span>
              <div>{feedback.message}</div>
            </div>
          )}

          {loading ? (
            <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--muted)" }}>
              Loading projects and environment hierarchies...
            </div>
          ) : projectList.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "40px" }}>
              <div style={{ fontSize: "32px", marginBottom: "12px" }}>📦</div>
              <h3 style={{ fontSize: "16px", marginBottom: "6px" }}>No projects created yet</h3>
              <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "20px" }}>
                Create your first project to configure development, staging, or production environments.
              </p>
              {canCreateProject && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setShowProjectModal(true)}
                >
                  Create Initial Project
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: "grid", gap: "20px" }}>
              {projectList.map((project) => (
                <div key={project.id} className="card">
                  <div className="card-header" style={{ marginBottom: "14px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <h2 className="card-title" style={{ fontSize: "16px" }}>{project.name}</h2>
                        {project.role && (
                          <span className={`badge badge-${project.role.toLowerCase()}`}>
                            {project.role}
                          </span>
                        )}
                        <code style={{ fontSize: "10px", background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>
                          slug: {project.slug}
                        </code>
                      </div>
                      <div className="card-subtitle">
                        {project.description || "No project description provided."}
                      </div>
                    </div>

                    {createPermissionEngine({ role: project.role }).canManageEnvironment() && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ fontSize: "11px", padding: "6px 12px" }}
                        onClick={() => {
                          setSelectedProjectId(project.id);
                          setShowEnvModal(true);
                        }}
                      >
                        + Add Environment
                      </button>
                    )}
                  </div>

                  <div style={{ borderTop: "1px solid var(--line)", paddingTop: "14px" }}>
                    <div style={{ fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "var(--muted)", marginBottom: "10px", textTransform: "uppercase" }}>
                      Environments ({(project.environments || []).length})
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "12px" }}>
                      {(project.environments || []).map((env) => (
                        <div
                          key={env.id}
                          style={{
                            border: "1px solid var(--line)",
                            borderRadius: "8px",
                            padding: "14px",
                            background: "#fafcfb",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                            <strong style={{ fontSize: "13px" }}>{env.name}</strong>
                            <span
                              className="badge"
                              style={{
                                background: env.type === "Production" ? "#fee2e2" : env.type === "Staging" ? "#fef3c7" : "#e0f2fe",
                                color: env.type === "Production" ? "#991b1b" : env.type === "Staging" ? "#92400e" : "#0369a1",
                                border: "1px solid transparent",
                              }}
                            >
                              {env.type}
                            </span>
                          </div>
                          <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "8px" }}>
                            {env.description || "No description provided."}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "10px", color: "var(--forest)", fontFamily: "'DM Mono', monospace" }}>
                            <span className="status-dot">Isolated</span>
                            <span>ID: {env.id.substring(0, 8)}...</span>
                          </div>
                          {env.can_delete && permissions.hasPermission("environment:delete") && (
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ marginTop: "10px", fontSize: "11px" }}
                              onClick={() => {
                                setPendingDeleteEnvironment(env);
                                setProductionConfirmation("");
                              }}
                            >
                              Delete environment
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Create Project Modal */}
      {showProjectModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>Create New Project</h3>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowProjectModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateProject}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Project Name *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Core LLM Gateway"
                    value={projName}
                    onChange={(e) => {
                      setProjName(e.target.value);
                      if (!projSlug) {
                        setProjSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                      }
                    }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Project Slug</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. core-llm-gateway"
                    value={projSlug}
                    onChange={(e) => setProjSlug(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Description (Optional)</label>
                  <textarea
                    rows={2}
                    className="form-textarea"
                    placeholder="Brief description of the project mission..."
                    value={projDesc}
                    onChange={(e) => setProjDesc(e.target.value)}
                  />
                </div>

                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "14px", marginTop: "14px" }}>
                  <div style={{ fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", marginBottom: "8px" }}>
                    INITIAL ENVIRONMENT
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Environment Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={initialEnvName}
                        onChange={(e) => setInitialEnvName(e.target.value)}
                      />
                    </div>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Type</label>
                      <select
                        className="form-select"
                        value={initialEnvType}
                        onChange={(e) => setInitialEnvType(e.target.value)}
                      >
                        <option value="Production">Production</option>
                        <option value="Staging">Staging</option>
                        <option value="Development">Development</option>
                        <option value="QA">QA</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowProjectModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Environment Modal */}
      {showEnvModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>Add Environment</h3>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowEnvModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateEnvironment}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Environment Name *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Staging or EU-West-Prod"
                    value={envName}
                    onChange={(e) => setEnvName(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Environment Type *</label>
                  <select
                    className="form-select"
                    value={envType}
                    onChange={(e) => setEnvType(e.target.value)}
                  >
                    <option value="Development">Development</option>
                    <option value="Staging">Staging</option>
                    <option value="Production">Production</option>
                    <option value="QA">QA</option>
                    <option value="UAT">UAT</option>
                    <option value="Custom">Custom</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    rows={2}
                    className="form-textarea"
                    placeholder="Dedicated staging cluster with production mirror"
                    value={envDesc}
                    onChange={(e) => setEnvDesc(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEnvModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? "Adding..." : "Add Environment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {pendingDeleteEnvironment && (
        <div className="modal-backdrop">
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-environment-title"
          >
            <div className="modal-header">
              <h2 id="delete-environment-title" style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>
                Delete {pendingDeleteEnvironment.type} environment
              </h2>
              <button
                type="button"
                className="btn btn-ghost"
                aria-label="Close delete confirmation"
                onClick={() => {
                  setPendingDeleteEnvironment(null);
                  setProductionConfirmation("");
                }}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleDeleteEnvironment}>
              <div className="modal-body">
                <p>
                  This permanently deletes <strong>{pendingDeleteEnvironment.name}</strong> and its environment membership.
                  This action cannot be undone.
                </p>
                {pendingDeleteEnvironment.type === "Production" && (
                  <div className="form-group">
                    <label className="form-label" htmlFor="production-environment-confirmation">
                      Type the environment slug <code>{pendingDeleteEnvironment.slug}</code> to confirm
                    </label>
                    <input
                      id="production-environment-confirmation"
                      className="form-input"
                      value={productionConfirmation}
                      onChange={(event) => setProductionConfirmation(event.target.value)}
                      required
                      autoComplete="off"
                    />
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setPendingDeleteEnvironment(null)}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting || (pendingDeleteEnvironment.type === "Production" && productionConfirmation !== pendingDeleteEnvironment.slug)}
                >
                  {submitting ? "Deleting…" : "Delete environment"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
