"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

interface InvitationDetails {
  id: string;
  email: string;
  organization_id: string;
  organization_name: string;
  project_id?: string | null;
  project_name?: string | null;
  environment_id?: string | null;
  environment_name?: string | null;
  role: string;
  status: string;
  is_expired: boolean;
  is_accepted: boolean;
  expires_at: string;
}

export default function InviteAcceptancePage() {
  const params = useParams();
  const router = useRouter();
  const token = params?.token as string;

  const [invitation, setInvitation] = useState<InvitationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [isAccepting, setIsAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (!token) {
      setErrorMsg("Invitation link is invalid.");
      setLoading(false);
      return;
    }
    const fetchInvitation = async () => {
      try {
        const res = await fetch(`/api/proxy/invitations/${token}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Invalid or expired invitation" }));
          throw new Error(err.detail || "Unable to retrieve invitation.");
        }
        const data = await res.json();
        setInvitation(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Error verifying invitation";
        setErrorMsg(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchInvitation();
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;
    setIsAccepting(true);
    setErrorMsg(null);
    setContextError(null);
    let membershipAccepted = false;
    try {
      const res = await fetch(`/api/proxy/invitations/${token}/accept`, {
        method: "POST",
      });
      if (res.status === 401 || res.status === 403) {
        const error = await res.json().catch(() => null);
        if (res.status === 401) {
          router.push(`/login?redirect=${encodeURIComponent(`/invite/${token}`)}`);
          return;
        }
        throw new Error(error?.detail || "Sign in with the email address that received this invitation.");
        return;
      }
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to accept invitation");
      }
      const result: {
        organization_id: string;
        project_id?: string | null;
        environment_id?: string | null;
      } = await res.json();
      setAccepted(true);
      membershipAccepted = true;
      const contextResponse = await fetch("/api/auth/switch-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: result.organization_id,
          project_id: result.project_id || undefined,
          environment_id: result.environment_id || undefined,
        }),
      });
      if (!contextResponse.ok) {
        const body = await contextResponse.json().catch(() => null);
        throw new Error(body?.error || body?.detail || "Unable to switch to the invited workspace.");
      }
      localStorage.setItem("agentops_active_org", result.organization_id);
      if (result.project_id) {
        localStorage.setItem(`agentops_proj_${result.organization_id}`, result.project_id);
      }
      if (result.environment_id) {
        if (result.project_id) {
          localStorage.setItem(`agentops_env_${result.project_id}`, result.environment_id);
        }
      }
      window.location.assign("/home");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Acceptance failed";
      if (membershipAccepted) {
        setContextError(msg);
      } else {
        setErrorMsg(msg);
      }
      setIsAccepting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #0a0f1d 0%, #0d1e17 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        fontFamily: "'Manrope', sans-serif",
      }}
    >
      <div
        style={{
          background: "#ffffff",
          borderRadius: "16px",
          width: "100%",
          maxWidth: "480px",
          padding: "36px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div
            style={{
              width: "44px",
              height: "44px",
              background: "#c7edcf",
              borderRadius: "12px",
              color: "#173e2d",
              fontWeight: "800",
              fontSize: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 12px",
            }}
          >
            AO
          </div>
          <h1 style={{ margin: "0 0 6px 0", fontSize: "22px", letterSpacing: "-0.03em" }}>
            Platform Invitation
          </h1>
          <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>
            You have been invited to collaborate on AgentOps
          </p>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px", color: "#64748b" }}>
            Validating cryptographic invitation token...
          </div>
        ) : errorMsg ? (
          <div>
            <div className="alert-banner error" style={{ marginBottom: "20px" }}>
              <span>⚠️</span>
              <div>{errorMsg}</div>
            </div>
            <div style={{ textAlign: "center", fontSize: "12px" }}>
              <Link
                href={token ? `/login?redirect=${encodeURIComponent(`/invite/${token}`)}` : "/login"}
                className="btn btn-secondary"
              >
                Sign in with invited account
              </Link>
            </div>
          </div>
        ) : accepted ? (
          <div style={{ textAlign: "center" }}>
            <div className="alert-banner success" style={{ marginBottom: "20px" }}>
              <span>✓</span>
              <div>
                Invitation accepted! Your membership is active.
              </div>
            </div>
            {contextError && (
              <div className="alert-banner error" role="alert" style={{ marginBottom: "20px" }}>
                <span>⚠️</span>
                <div>
                  The invitation was accepted, but the workspace could not be selected: {contextError}
                  {" "}<Link href="/organizations">Choose a workspace</Link>
                </div>
              </div>
            )}
          </div>
        ) : invitation ? (
          <div style={{ display: "grid", gap: "20px" }}>
            <div
              style={{
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                padding: "16px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "11px", color: "#64748b" }}>Invited Email:</span>
                <strong style={{ fontSize: "12px" }}>{invitation.email}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "11px", color: "#64748b" }}>Organization:</span>
                <strong style={{ fontSize: "12px" }}>{invitation.organization_name}</strong>
              </div>
              {invitation.project_id && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", color: "#64748b" }}>Target Project:</span>
                  <strong style={{ fontSize: "12px" }}>{invitation.project_name || invitation.project_id}</strong>
                </div>
              )}
              {invitation.environment_id && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ fontSize: "11px", color: "#64748b" }}>Target Environment:</span>
                  <strong style={{ fontSize: "12px" }}>{invitation.environment_name || invitation.environment_id}</strong>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: "11px", color: "#64748b" }}>Assigned Role:</span>
                <span className="badge badge-admin">{invitation.role}</span>
              </div>
            </div>

            {invitation.is_expired || invitation.status === "expired" ? (
              <div className="alert-banner error" role="status">
                <span>⚠️</span><div>This invitation has expired. Ask your organization administrator for a new invitation.</div>
              </div>
            ) : invitation.is_accepted || invitation.status === "accepted" ? (
              <div className="alert-banner info" role="status">
                <span>ℹ️</span><div>This invitation has already been accepted.</div>
              </div>
            ) : (
              <>
                <div className="alert-banner info" style={{ fontSize: "11px", margin: 0 }}>
                  <span>ℹ️</span>
                  <div>Sign in with the invited email address ({invitation.email}) to accept this invitation.</div>
                </div>

                <div style={{ display: "grid", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={handleAccept}
                    disabled={isAccepting}
                    className="btn btn-primary"
                    style={{ width: "100%", padding: "12px" }}
                  >
                    {isAccepting ? "Activating Membership..." : "Accept Invitation & Join Workspace"}
                  </button>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#64748b" }}>
                    <span>Not signed in?</span>
                    <Link href={`/login?redirect=${encodeURIComponent(`/invite/${token}`)}`} style={{ color: "#155c43", fontWeight: "700" }}>
                      Sign in with Keycloak →
                    </Link>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
