"use client";

import { useEffect, useState } from "react";

interface SecurityOverview {
  auth_provider: string;
  oidc_status: string;
  oidc_realm: string;
  oidc_client_id: string;
  mfa_status: string;
  tenant_isolation_mode: string;
  active_user: {
    subject_id: string;
    email: string;
    display_name: string;
    tenant_id: string;
  };
  roles: string[];
  permissions_count: number;
  session_id: string | null;
  last_login: string;
  security_events_count: number;
  zero_trust_assertions: string;
  recent_audit_events: Array<{
    id: string;
    action: string;
    actor_email: string;
    resource_type: string;
    created_at: string;
  }>;
}

export function SecurityDashboardView() {
  const [data, setData] = useState<SecurityOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function fetchSecurity() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/proxy/security/overview", { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.detail ?? `Security overview request failed (${response.status}).`);
        }
        setData(await response.json() as SecurityOverview);
      } catch (err: unknown) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to load security overview.");
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }
    void fetchSecurity();
    return () => controller.abort();
  }, []);

  if (isLoading) return <p className="data-note" role="status">Loading identity and access status…</p>;
  if (error) return <section className="panel error-panel" role="alert"><h2>Security overview unavailable</h2><p>{error}</p></section>;
  if (!data) return null;

  return (
    <section className="panel security-overview" aria-labelledby="security-overview-title">
      <div className="panel-header">
        <div>
          <h2 id="security-overview-title">Identity and access status</h2>
          <p className="data-note">Current authenticated session and tenant-scoped audit data.</p>
        </div>
      </div>
      <div className="security-overview-grid">
        <article className="security-overview-card">
          <span className="metric-label">Identity provider</span>
          <strong>{data.auth_provider}</strong>
          <span>{data.oidc_status}</span>
          <small>Realm: {data.oidc_realm || "Not reported"} · Client: {data.oidc_client_id || "Not reported"}</small>
        </article>
        <article className="security-overview-card">
          <span className="metric-label">Authenticated user</span>
          <strong>{data.active_user.display_name}</strong>
          <span>{data.active_user.email}</span>
          <small>Last login: {data.last_login || "Not available"} · MFA: {data.mfa_status}</small>
        </article>
        <article className="security-overview-card">
          <span className="metric-label">Access scope</span>
          <strong>{data.tenant_isolation_mode}</strong>
          <span>{data.permissions_count} granted permissions</span>
          <small>{data.roles.length ? data.roles.join(", ") : "No roles reported"} · Tenant: {data.active_user.tenant_id}</small>
        </article>
      </div>
      <div className="security-audit">
        <div className="panel-header">
          <h3>Recent audit events</h3>
          <span className="panel-link">{data.security_events_count} events reported</span>
        </div>
        {data.recent_audit_events.length === 0
          ? <p className="empty-state">No audit events are available for this scope.</p>
          : <div className="security-audit-list">
            {data.recent_audit_events.map((event) => (
              <article className="security-audit-row" key={event.id}>
                <div><strong>{event.action}</strong><span>{event.actor_email} · {event.resource_type}</span></div>
                <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
              </article>
            ))}
          </div>}
      </div>
    </section>
  );
}
