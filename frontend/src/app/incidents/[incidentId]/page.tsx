"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { Navigation } from "../../../components/navigation";
import { SystemStatus } from "../../../components/system-status";
import { ContextGuard } from "../../../components/context-guard";
import { investigateIncident, type InvestigationResponse } from "../../../lib/api";

export default function IncidentInvestigationPage({ params }: { params: Promise<{ incidentId: string }> }) {
  const { incidentId } = use(params);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInvestigation = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await investigateIncident(incidentId, signal);
      setInvestigation(result);
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : "Unable to load the incident investigation.");
        setInvestigation(null);
      }
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadInvestigation(controller.signal);
    return () => controller.abort();
  }, [loadInvestigation]);

  const correlated = investigation?.incident;
  const incident = correlated?.incident;

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div className="topbar-context">
            <span className="breadcrumb">Operations / Incidents <strong>/ Investigation</strong></span>
          </div>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Incident investigation">
            <section className="page-heading">
              <div>
                <span className="kicker">Incident intelligence</span>
                <h1>{incident?.title || "Incident investigation"}</h1>
                <p className="lede">Incident <code>{incidentId}</code> · Evidence and correlation from the incident service.</p>
              </div>
              <div className="page-actions">
                <Link href="/incidents" className="btn btn-secondary">Back to incidents</Link>
                {!isLoading && <button type="button" className="btn btn-primary" onClick={() => void loadInvestigation()}>Run investigation again</button>}
              </div>
            </section>

            {isLoading && <p className="data-note" role="status">Running the authorized incident investigation…</p>}
            {error && (
              <section className="panel error-panel" role="alert">
                <p>{error}</p>
                <button type="button" className="btn btn-secondary" onClick={() => void loadInvestigation()}>Retry investigation</button>
              </section>
            )}

            {investigation && incident && correlated && !isLoading && (
              <>
                <section className="metrics" aria-label="Incident summary">
                  <article className="metric"><span className="metric-label">Severity</span><div className="metric-value">{incident.severity}</div><span className="metric-note">{incident.status}</span></article>
                  <article className="metric"><span className="metric-label">Service</span><div className="metric-value metric-value-text">{incident.service}</div><span className="metric-note">Current incident target</span></article>
                  <article className="metric"><span className="metric-label">Correlation confidence</span><div className="metric-value">{Math.round(correlated.confidence * 100)}%</div><span className="metric-note">Based on collected evidence</span></article>
                  <article className="metric"><span className="metric-label">Evidence items</span><div className="metric-value">{correlated.evidence.length}</div><span className="metric-note">Run {investigation.run_id}</span></article>
                </section>

                <section className="dashboard-grid">
                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Investigation findings</h2><span className="panel-link">{investigation.status}</span></div>
                    {investigation.findings.map((finding, index) => <p className="finding-item" key={`${index}-${finding}`}>{finding}</p>)}
                    {investigation.findings.length === 0 && <p className="empty-state">The investigation did not return findings.</p>}
                    {investigation.recommendation && (
                      <div className="recommendation-callout"><strong>Recommendation</strong><p>{investigation.recommendation}</p></div>
                    )}
                    {correlated.hypotheses.length > 0 && (
                      <div className="result-list">
                        <h3>Hypotheses</h3>
                        <ul>{correlated.hypotheses.map((hypothesis) => <li key={hypothesis}>{hypothesis}</li>)}</ul>
                      </div>
                    )}
                    {correlated.recommended_steps.length > 0 && (
                      <div className="result-list">
                        <h3>Suggested next steps</h3>
                        <ol>{correlated.recommended_steps.map((step) => <li key={step}>{step}</li>)}</ol>
                      </div>
                    )}
                  </article>

                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Correlated timeline</h2><span className="panel-link">{correlated.timeline.length} events</span></div>
                    {correlated.timeline.map((event, index) => (
                      <div className="timeline-row" key={`${event.timestamp}-${index}`}>
                        <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time>
                        <div><strong>{event.title}</strong><span>{event.event_type} · {event.source}</span></div>
                      </div>
                    ))}
                    {correlated.timeline.length === 0 && <p className="empty-state">No correlated events are available.</p>}
                  </article>
                </section>

                <section className="panel panel-wide evidence-panel">
                  <div className="panel-header"><h2>Evidence</h2><span className="panel-link">Collected from configured sources</span></div>
                  {correlated.evidence.map((item, index) => (
                    <details className="evidence-item" key={`${item.source}-${index}`}>
                      <summary><strong>{item.type}</strong><span>{item.source}</span></summary>
                      <pre>{JSON.stringify(item.data, null, 2)}</pre>
                    </details>
                  ))}
                  {correlated.evidence.length === 0 && <p className="empty-state">No evidence was returned for this investigation.</p>}
                </section>
              </>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
