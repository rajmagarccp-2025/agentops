"use client";

import { useState } from "react";
import Link from "next/link";
import { Navigation } from "../../components/navigation";
import { useWorkspace } from "../../state/workspace-context";

export default function OrganizationsPage() {
  const { organizations, currentOrg, switchOrg, setActiveOrg, effectiveRole, refreshWorkspace, isLoading, workspaceError } = useWorkspace();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [switchingOrgId, setSwitchingOrgId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch("/api/proxy/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          slug: slug.trim() || undefined,
          description: description.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create organization");
      }

      const created = await res.json();
      setFeedback({ type: "success", message: `Organization ${name} created successfully!` });
      setShowModal(false);
      setName("");
      setSlug("");
      setDescription("");
      await refreshWorkspace();
      const switched = await setActiveOrg(created);
      if (!switched) {
        setFeedback({ type: "error", message: "Organization was created, but its workspace context could not be selected." });
        return;
      }
      await refreshWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Creation failed";
      setFeedback({ type: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSwitchOrg = async (organizationId: string) => {
    setSwitchingOrgId(organizationId);
    setFeedback(null);
    try {
      const switched = await switchOrg(organizationId);
      if (!switched) {
        setFeedback({ type: "error", message: "Unable to switch organization. Review the workspace context error and retry." });
      }
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Unable to switch organization.",
      });
    } finally {
      setSwitchingOrgId(null);
    }
  };

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">
              Workspace <strong>/ Organizations</strong>
            </span>
          </div>
          <div className="topbar-actions">
            <span className={`badge badge-${effectiveRole.toLowerCase()}`}>
              Your Role: {effectiveRole}
            </span>
          </div>
        </header>

        <main className="main-content">
          <section className="page-heading">
            <div>
              <span className="kicker">Multi-Tenant Management</span>
              <h1>Your Organizations</h1>
              <p className="lede">
                Organizations establish strict tenant isolation boundaries. You can belong to multiple organizations.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowModal(true)}
            >
              + Create Organization
            </button>
          </section>

          {feedback && (
            <div className={`alert-banner ${feedback.type}`} style={{ marginBottom: "20px" }}>
              <span>{feedback.type === "success" ? "✓" : "⚠️"}</span>
              <div>{feedback.message}</div>
            </div>
          )}
          {workspaceError && <div className="alert-banner error" role="alert" style={{ marginBottom: "20px" }}>{workspaceError}</div>}

          {isLoading ? <p className="data-note" role="status">Loading organizations…</p> : organizations.length === 0 ? <div className="empty-state">No organizations are associated with this account yet. Create one or accept an invitation to get started.</div> : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "16px" }}>
            {organizations.map((org) => {
              const isSelected = currentOrg?.id === org.id;
              return (
                <div
                  key={org.id}
                  className="card"
                  style={{
                    borderColor: isSelected ? "var(--forest)" : "var(--line)",
                    boxShadow: isSelected ? "0 0 0 2px var(--mint)" : undefined,
                  }}
                >
                  <div className="card-header">
                    <div>
                      <h3 className="card-title" style={{ fontSize: "16px" }}>{org.name}</h3>
                      <div className="card-subtitle">ID: {org.id}</div>
                    </div>
                    {isSelected ? (
                      <span className="badge badge-admin">Active</span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ fontSize: "11px", padding: "4px 10px" }}
                        onClick={() => void handleSwitchOrg(org.id)}
                        disabled={switchingOrgId === org.id}
                      >
                        {switchingOrgId === org.id ? "Switching…" : "Switch"}
                      </button>
                    )}
                  </div>

                  <p style={{ fontSize: "12px", color: "var(--muted)", margin: "0 0 16px 0", minHeight: "36px" }}>
                    {org.description || "No description provided."}
                  </p>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--line)", paddingTop: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <span className={`badge badge-${org.role.toLowerCase()}`}>Role: {org.role}</span>
                      {org.is_owner && <span className="badge badge-owner">Owner</span>}
                    </div>

                    {isSelected
                      ? <Link href="/members" style={{ fontSize: "11px", color: "var(--forest)", fontWeight: "600" }}>Team & Access →</Link>
                      : <span className="data-note">Switch to manage access</span>}
                  </div>
                </div>
              );
            })}
          </div>
          }
        </main>
      </div>

      {/* Create Org Modal */}
      {showModal && (
        <div className="modal-backdrop">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="create-organization-title">
            <div className="modal-header">
              <h3 id="create-organization-title" style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>Create New Organization</h3>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateOrg}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Organization Name *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Acme Cloud Corp"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      if (!slug) {
                        setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                      }
                    }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Slug</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. acme-cloud-corp"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                  />
                  <span className="form-hint">Unique identifier used for subdomains and routing.</span>
                </div>

                <div className="form-group">
                  <label className="form-label">Description (Optional)</label>
                  <textarea
                    rows={2}
                    className="form-textarea"
                    placeholder="Enterprise tenant for production operations"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div className="alert-banner info" style={{ fontSize: "11px", margin: 0 }}>
                  <span>ℹ️</span>
                  <div>
                    Creating this organization will automatically assign you as <strong>Owner</strong> and <strong>ADMIN</strong>.
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? "Creating..." : "Create Organization"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
