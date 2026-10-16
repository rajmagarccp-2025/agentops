"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Navigation } from "../../components/navigation";
import { useWorkspace } from "../../state/workspace-context";
import { canManageMembers } from "../../lib/permissions";

interface Member {
  id: string;
  membership_id?: string;
  email: string;
  name?: string | null;
  role: string;
  is_owner?: boolean;
  joined_at?: string;
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
  token: string;
  project_id?: string | null;
  environment_id?: string | null;
  expires_at: string;
  created_at: string;
}

export default function MembersPage() {
  const { currentOrg, effectiveRole } = useWorkspace();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("READ");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const canManage = canManageMembers(effectiveRole);

  const fetchData = useCallback(async () => {
    if (!currentOrg?.id) {
      setMembers([]);
      setInvitations([]);
      setLoadingError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadingError(null);
    try {
      const [membersRes, invitesRes] = await Promise.all([
        fetch(`/api/proxy/organizations/${currentOrg.id}/members`),
        canManage ? fetch(`/api/proxy/invitations/org/${currentOrg.id}`) : Promise.resolve(null),
      ]);
      if (!membersRes.ok || (invitesRes && !invitesRes.ok)) {
        const failedResponse = !membersRes.ok ? membersRes : invitesRes!;
        const detail = await failedResponse.json().catch(() => null);
        throw new Error(detail?.detail || `Unable to load organization access data (${failedResponse.status}).`);
      }
      const [memberData, invitationData] = await Promise.all([
        membersRes.json(),
        invitesRes ? invitesRes.json() : Promise.resolve([]),
      ]);
      setMembers(memberData.map((member: Omit<Member, "id"> & { user_id: string }) => ({ ...member, id: member.user_id })));
      setInvitations(invitationData);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unable to load organization access data.";
      setMembers([]);
      setInvitations([]);
      setLoadingError(message);
    } finally {
      setLoading(false);
    }
  }, [canManage, currentOrg?.id]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg?.id || !inviteEmail.trim()) return;
    setIsSubmitting(true);
    setFeedback(null);

    try {
      const res = await fetch("/api/proxy/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: currentOrg.id,
          email: inviteEmail.trim(),
          role: inviteRole,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to dispatch invitation");
      }

      const newInvite: { invite_url?: string } = await res.json();
      if (!newInvite.invite_url) {
        throw new Error("Invitation was created, but the server did not return a sharing link.");
      }
      setInviteLink(new URL(newInvite.invite_url, window.location.origin).toString());
      setFeedback({ type: "success", message: `Invitation created for ${inviteEmail}. Share the link with the invitee securely.` });
      setShowInviteModal(false);
      setInviteEmail("");
      void fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invitation failed";
      setFeedback({ type: "error", message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (!currentOrg?.id) return;
    try {
      const res = await fetch(`/api/proxy/organizations/${currentOrg.id}/members/${userId}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update member role");
      }
      setFeedback({ type: "success", message: "Member role updated successfully." });
      void fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Update failed";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleRemoveMember = async (userId: string, email: string) => {
    if (!currentOrg?.id) return;
    if (!confirm(`Are you sure you want to remove ${email} from ${currentOrg.name}?`)) return;

    try {
      const res = await fetch(`/api/proxy/organizations/${currentOrg.id}/members/${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to remove member");
      }
      setFeedback({ type: "success", message: `Member ${email} removed.` });
      void fetchData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Remove failed";
      setFeedback({ type: "error", message: msg });
    }
  };

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">
              Workspace <strong>/ {currentOrg?.name}</strong> / Members
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
              <span className="kicker">Access Management & RBAC</span>
              <h1>Organization Members</h1>
              <p className="lede">
                {currentOrg
                  ? <>Manage team access, role assignments, and invitations for <strong>{currentOrg.name}</strong>.</>
                  : "Select or create an organization to manage team access and invitations."}
              </p>
            </div>

            {canManage && currentOrg && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowInviteModal(true)}
              >
                + Invite New Member
              </button>
            )}
          </section>
          {!currentOrg && <section className="panel empty-state"><p>No organization is selected.</p><Link className="btn btn-primary" href="/organizations">Choose organization</Link></section>}

          {loadingError && (
            <section className="panel error-panel" role="alert" style={{ marginBottom: "20px" }}>
              <h2>Organization access data unavailable</h2>
              <p>{loadingError}</p>
              <button type="button" className="btn btn-secondary" onClick={() => void fetchData()} disabled={loading}>
                {loading ? "Retrying…" : "Retry"}
              </button>
            </section>
          )}

          {feedback && (
            <div className={`alert-banner ${feedback.type}`} style={{ marginBottom: "20px" }}>
              <span>{feedback.type === "success" ? "✓" : "⚠️"}</span>
              <div>{feedback.message}</div>
            </div>
          )}

          {inviteLink && (
            <section className="panel" aria-labelledby="invite-link-title" style={{ marginBottom: "20px" }}>
              <h2 id="invite-link-title">Invitation link</h2>
              <p>Share this link securely with the invited person. It expires according to the invitation policy.</p>
              <input
                type="url"
                className="form-input"
                aria-label="Invitation link"
                readOnly
                value={inviteLink}
                onFocus={(event) => event.currentTarget.select()}
              />
            </section>
          )}

          {!canManage && (
            <div className="alert-banner info" style={{ marginBottom: "24px" }}>
              <span>ℹ️</span>
              <div>
                <strong>Read-Only Member View:</strong> You are currently signed in with the <strong>{effectiveRole}</strong> role.
                Only organization administrators can invite members, assign roles, or revoke memberships.
              </div>
            </div>
          )}

          {/* Active Members Table */}
          <div className="card" style={{ marginBottom: "32px" }}>
            <div className="card-header">
              <div>
                <h2 className="card-title">Active Members ({members.length})</h2>
                <div className="card-subtitle">Users with active tenant authorization</div>
              </div>
            </div>

            <div className="table-container">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Ownership</th>
                    <th>Status</th>
                    {canManage && <th style={{ textAlign: "right" }}>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={canManage ? 5 : 4} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                        Loading membership records...
                      </td>
                    </tr>
                  ) : loadingError ? (
                    <tr>
                      <td colSpan={canManage ? 5 : 4} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                        Membership data could not be loaded.
                      </td>
                    </tr>
                  ) : members.length === 0 ? (
                    <tr>
                      <td colSpan={canManage ? 5 : 4} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                        No members found in this tenant.
                      </td>
                    </tr>
                  ) : (
                    members.map((member) => (
                      <tr key={member.id}>
                        <td>
                          <strong>{member.name || member.email}</strong>
                          <div style={{ fontSize: "10px", color: "var(--muted)", fontFamily: "'DM Mono', monospace" }}>
                            {member.email}
                          </div>
                        </td>
                        <td>
                          {canManage && !member.is_owner ? (
                            <select
                              value={member.role}
                              onChange={(e) => handleRoleChange(member.id, e.target.value)}
                              className="form-select"
                              style={{ padding: "4px 8px", fontSize: "11px", width: "110px" }}
                            >
                              <option value="ADMIN">ADMIN</option>
                              <option value="WRITE">WRITE</option>
                              <option value="READ">READ</option>
                            </select>
                          ) : (
                            <span className={`badge badge-${member.role.toLowerCase()}`}>
                              {member.role}
                            </span>
                          )}
                        </td>
                        <td>
                          {member.is_owner ? (
                            <span className="badge badge-owner">Owner</span>
                          ) : (
                            <span style={{ fontSize: "11px", color: "var(--muted)" }}>Member</span>
                          )}
                        </td>
                        <td>
                          <span className="status-dot">Active</span>
                        </td>
                        {canManage && (
                          <td style={{ textAlign: "right" }}>
                            {!member.is_owner && (
                              <button
                                type="button"
                                className="btn btn-ghost"
                                style={{ color: "var(--red)", fontSize: "11px", padding: "4px 8px" }}
                                onClick={() => handleRemoveMember(member.id, member.email)}
                              >
                                Remove
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Invitation Records Table */}
          {canManage && <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Invitations ({invitations.length})</h2>
                <div className="card-subtitle">Invitation records for this organization</div>
              </div>
            </div>

            <div className="table-container">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>Invited Email</th>
                    <th>Role</th>
                    <th>Token Link</th>
                    <th>Expires</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                        Loading invitation records...
                      </td>
                    </tr>
                  ) : loadingError ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                        Invitation data could not be loaded.
                      </td>
                    </tr>
                  ) : invitations.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                        No invitations found.
                      </td>
                    </tr>
                  ) : (
                    invitations.map((inv) => (
                      <tr key={inv.id}>
                        <td>
                          <strong>{inv.email}</strong>
                        </td>
                        <td>
                          <span className="badge badge-admin">{inv.role}</span>
                        </td>
                        <td>
                          <Link href={`/invite/${encodeURIComponent(inv.token)}`} target="_blank" rel="noreferrer">
                            Open invitation
                          </Link>
                        </td>
                        <td style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "'DM Mono', monospace" }}>
                          {new Date(inv.expires_at).toLocaleDateString()}
                        </td>
                        <td>
                          <span className={`badge badge-${inv.status.toLowerCase()}`}>{inv.status}</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>}
        </main>
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <div className="modal-backdrop">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="invite-modal-title">
            <div className="modal-header">
              <h3 id="invite-modal-title" style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>Invite Member</h3>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowInviteModal(false)}
                aria-label="Close invitation form"
                style={{ fontSize: "16px", padding: "4px 8px" }}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSendInvite}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label" htmlFor="invite-email">Collaborator Email *</label>
                  <input
                    id="invite-email"
                    type="email"
                    required
                    className="form-input"
                    placeholder="teammate@enterprise.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                  />
                  <span className="form-hint">
                    Keycloak OIDC will authenticate the user before granting access.
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="invite-role">Role Assignment *</label>
                  <select
                    id="invite-role"
                    className="form-select"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                  >
                    <option value="READ">READ (Strict read-only, AI query restricted)</option>
                    <option value="WRITE">WRITE (Operator write access, no member management)</option>
                    <option value="ADMIN">ADMIN (Full tenant administration)</option>
                  </select>
                </div>

                <div className="alert-banner info" style={{ fontSize: "11px", margin: 0 }}>
                  <span>ℹ️</span>
                  <div>
                    An invitation token with a 7-day expiration will be generated and assigned to this tenant.
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowInviteModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Creating Invitation..." : "Create Invitation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
