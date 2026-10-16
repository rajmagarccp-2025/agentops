"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import {
  fetchFinOpsRecommendations,
  fetchFinOpsSummary,
  ingestCostRecord,
  type FinOpsRecommendation,
  type FinOpsSummary,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

export default function FinOpsPage() {
  const { activeEnvironment, permissions } = useWorkspace();
  const [summary, setSummary] = useState<FinOpsSummary | null>(null);
  const [recommendations, setRecommendations] = useState<FinOpsRecommendation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadFinOps = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, nextRecommendations] = await Promise.all([
        fetchFinOpsSummary(signal),
        fetchFinOpsRecommendations(signal),
      ]);
      setSummary(nextSummary);
      setRecommendations(nextRecommendations);
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : "Unable to load FinOps data.");
        setSummary(null);
        setRecommendations(null);
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadFinOps(controller.signal);
    return () => controller.abort();
  }, [loadFinOps]);

  async function submitCost(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      await ingestCostRecord({
        period: String(form.get("period") || ""),
        provider: String(form.get("provider") || ""),
        account: String(form.get("account") || "").trim(),
        service: String(form.get("service") || "").trim(),
        environment: String(form.get("environment") || "").trim(),
        amount_usd: Number(form.get("amount_usd")),
      });
      setShowForm(false);
      event.currentTarget.reset();
      await loadFinOps();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to record cost data.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">Operations <strong>/ FinOps</strong></span>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="FinOps and cost intelligence">
            <GlobalContextSelector />
            <section className="page-heading">
              <div><span className="kicker">Cost intelligence</span><h1>FinOps & Cloud Cost Governance</h1><p className="lede">Review recorded spend and governed optimization opportunities.</p></div>
              {permissions.hasPermission("finops:write") && (
                <button type="button" className="primary-button" onClick={() => setShowForm((open) => !open)}>
                  {showForm ? "Cancel" : "Record cost data"}
                </button>
              )}
            </section>

            {error && <section className="panel error-panel" role="alert"><p>{error}</p><button type="button" className="btn btn-secondary" onClick={() => void loadFinOps()}>Retry</button></section>}
            {showForm && (
              <form className="panel create-incident-form" onSubmit={submitCost}>
                <h2>Record a cost entry</h2>
                <div className="field-row">
                  <label className="field"><span>Billing period</span><input name="period" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></label>
                  <label className="field"><span>Provider</span><select name="provider" required defaultValue="aws"><option value="aws">AWS</option><option value="azure">Azure</option><option value="gcp">Google Cloud</option><option value="kubernetes">Kubernetes</option></select></label>
                </div>
                <div className="field-row">
                  <label className="field"><span>Account</span><input name="account" required maxLength={200} /></label>
                  <label className="field"><span>Service</span><input name="service" required maxLength={200} /></label>
                </div>
                <div className="field-row">
                  <label className="field"><span>Environment</span><input name="environment" required maxLength={100} defaultValue={activeEnvironment?.name ?? ""} /></label>
                  <label className="field"><span>Amount (USD)</span><input name="amount_usd" type="number" min="0" step="0.01" required /></label>
                </div>
                <button type="submit" className="primary-button" disabled={submitting}>{submitting ? "Saving…" : "Save cost record"}</button>
              </form>
            )}

            {loading && <p className="data-note" role="status">Loading cost and utilization signals…</p>}
            {summary && recommendations && !loading && (
              <>
                <section className="metrics" aria-label="FinOps summary">
                  <article className="metric"><span className="metric-label">Tracked spend</span><div className="metric-value">${summary.total_cost_usd.toLocaleString()}</div><span className="metric-note">Recorded cost data</span></article>
                  <article className="metric"><span className="metric-label">Next month forecast</span><div className="metric-value">${summary.forecast_next_month_usd.toLocaleString()}</div><span className="metric-note">Based on observed costs</span></article>
                  <article className="metric"><span className="metric-label">Utilization records</span><div className="metric-value">{summary.utilization_records}</div><span className="metric-note">Resource observations</span></article>
                  <article className="metric"><span className="metric-label">Cost anomalies</span><div className="metric-value">{summary.anomaly_count}</div><span className={summary.anomaly_count ? "metric-note warning" : "metric-note"}>Observed signals</span></article>
                </section>
                <section className="dashboard-grid">
                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Cost by service</h2><span className="panel-link">Current tenant</span></div>
                    {Object.entries(summary.cost_by_service).map(([service, amount]) => (
                      <div className="finops-bar" key={service}>
                        <div><strong>{service}</strong><span>${amount.toLocaleString()}</span></div>
                        <i aria-label={`${service} share of tracked spend`}><b style={{ width: `${Math.min(100, (amount / Math.max(summary.total_cost_usd, 1)) * 100)}%` }} /></i>
                      </div>
                    ))}
                    {Object.keys(summary.cost_by_service).length === 0 && <p className="empty-state">No cost records are available for this tenant.</p>}
                  </article>
                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Recommendations</h2><span className="panel-link">Review before action</span></div>
                    {recommendations.map((recommendation) => (
                      <div className="recommendation-row" key={recommendation.id}>
                        <div><strong>{recommendation.title}</strong><span>{recommendation.rationale}</span></div>
                        <b>${recommendation.estimated_monthly_savings_usd.toLocaleString()}/mo</b>
                      </div>
                    ))}
                    {recommendations.length === 0 && <p className="empty-state">No optimization recommendations are available.</p>}
                  </article>
                </section>
              </>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
