"use client";

import { useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { SecurityDashboardView } from "../../components/security-dashboard-view";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import { fetchSecurityInvestigation, type SecurityInvestigation } from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

export default function SecurityPage() {
  const { permissions } = useWorkspace();
  const canInvestigate = permissions.hasPermission("security:investigate");
  const [investigation, setInvestigation] = useState<SecurityInvestigation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runInvestigation = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setInvestigation(await fetchSecurityInvestigation(signal));
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : "Security investigation failed.");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canInvestigate) return;
    const controller = new AbortController();
    void runInvestigation(controller.signal);
    return () => controller.abort();
  }, [canInvestigate, runInvestigation]);

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar"><span className="breadcrumb">Governance <strong>/ Security</strong></span><div className="topbar-actions"><SystemStatus /></div></header>
        <main className="main-content">
          <ContextGuard featureName="Security">
            <GlobalContextSelector />
            <section className="page-heading">
              <div>
                <span className="kicker">Security & compliance</span>
                <h1>Security & Hierarchical RBAC</h1>
                <p className="lede">Review authenticated identity, access scope, audit events, and tenant-scoped security findings.</p>
              </div>
              {canInvestigate && <button type="button" className="primary-button" onClick={() => void runInvestigation()} disabled={loading}>{loading ? "Investigating…" : investigation ? "Run investigation again" : "Run investigation"}</button>}
            </section>
            {!canInvestigate && <section className="panel permission-panel" role="status"><h2>Investigation access required</h2><p>Your role does not have permission to run security investigations. Contact an organization administrator if this access is needed.</p></section>}
            {canInvestigate && <SecurityDashboardView />}
            {canInvestigate && error && <section className="panel error-panel" role="alert"><h2>Investigation unavailable</h2><p>{error}</p><button type="button" className="btn btn-secondary" onClick={() => void runInvestigation()}>Retry</button></section>}
            {canInvestigate && investigation && (
              <>
                <section className="metrics" aria-label="Security investigation summary">
                  <article className="metric"><span className="metric-label">Events analyzed</span><div className="metric-value">{investigation.event_count}</div><span className="metric-note">Tenant scope</span></article>
                  <article className="metric"><span className="metric-label">Highest severity</span><div className="metric-value">{investigation.highest_severity}/5</div><span className="metric-note">Investigation result</span></article>
                  <article className="metric"><span className="metric-label">Findings</span><div className="metric-value">{investigation.findings.length}</div><span className="metric-note">Review evidence and recommendations</span></article>
                </section>
                <section className="panel panel-wide">
                  <div className="panel-header"><h2>Findings</h2><span className="panel-link">Investigation output</span></div>
                  {investigation.findings.map((finding) => (
                    <article className="security-row" key={finding.event_id}>
                      <span className={`security-severity severity-${finding.severity}`}>S{finding.severity}</span>
                      <div><strong>{finding.title}</strong><span>{finding.recommended_action}</span><small>{Math.round(finding.confidence * 100)}% confidence · approval required: {finding.requires_approval ? "yes" : "no"}</small></div>
                    </article>
                  ))}
                  {investigation.findings.length === 0 && <p className="empty-state">The investigation returned no findings.</p>}
                </section>
              </>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
