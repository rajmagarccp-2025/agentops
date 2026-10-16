"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import {
  createLearningFeedback,
  fetchLearningFeedback,
  fetchVerifications,
  type LearningRecord,
  type VerificationResult,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

export default function LearningPage() {
  const { permissions } = useWorkspace();
  const [verifications, setVerifications] = useState<VerificationResult[] | null>(null);
  const [feedback, setFeedback] = useState<LearningRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadLearning = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [nextVerifications, nextFeedback] = await Promise.all([
        fetchVerifications(signal),
        fetchLearningFeedback(signal),
      ]);
      setVerifications(nextVerifications);
      setFeedback(nextFeedback);
    } catch (err: unknown) {
      if (!signal?.aborted) setError(err instanceof Error ? err.message : "Unable to load learning data.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadLearning(controller.signal);
    return () => controller.abort();
  }, [loadLearning]);

  async function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSubmitting(true);
    setError(null);
    try {
      const record = await createLearningFeedback({
        remediation_id: String(form.get("remediation_id") || "").trim(),
        useful: form.get("useful") === "true",
        notes: String(form.get("notes") || "").trim(),
        labels: String(form.get("labels") || "").split(",").map((label) => label.trim()).filter(Boolean),
      });
      setFeedback((current) => [record, ...(current ?? [])]);
      setShowForm(false);
      formElement.reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to save operator feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  const recovered = verifications?.filter((item) => item.recovered).length ?? 0;
  const averageConfidence = verifications?.length
    ? verifications.reduce((sum, item) => sum + item.confidence, 0) / verifications.length
    : null;

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar"><span className="breadcrumb">Governance <strong>/ Learning</strong></span><div className="topbar-actions"><SystemStatus /></div></header>
        <main className="main-content">
          <ContextGuard featureName="Verification and learning">
            <section className="page-heading">
              <div><span className="kicker">Closed-loop operations</span><h1>Verification & learning</h1><p className="lede">Measure remediation outcomes and capture operator feedback for future decisions.</p></div>
              {permissions.hasPermission("learning:write") && <button type="button" className="primary-button" onClick={() => setShowForm((open) => !open)}>{showForm ? "Cancel" : "Add feedback"}</button>}
            </section>
            {error && <section className="panel error-panel" role="alert"><p>{error}</p><button type="button" className="btn btn-secondary" onClick={() => void loadLearning()}>Retry</button></section>}
            {showForm && (
              <form className="panel create-incident-form" onSubmit={submitFeedback}>
                <h2>Record operator feedback</h2>
                <p className="data-note">Feedback is attached to an existing remediation record in this workspace.</p>
                <label className="field"><span>Remediation record ID</span><input name="remediation_id" required /></label>
                <label className="field"><span>Assessment</span><select name="useful" defaultValue="true"><option value="true">Useful</option><option value="false">Needs review</option></select></label>
                <label className="field"><span>Notes</span><textarea name="notes" rows={4} maxLength={5_000} /></label>
                <label className="field"><span>Labels (comma separated)</span><input name="labels" placeholder="accurate, actionable" /></label>
                <button type="submit" className="primary-button" disabled={submitting}>{submitting ? "Saving…" : "Save feedback"}</button>
              </form>
            )}
            {loading && <p className="data-note" role="status">Loading verification outcomes…</p>}
            {verifications && feedback && !loading && (
              <>
                <section className="metrics" aria-label="Learning summary">
                  <article className="metric"><span className="metric-label">Verified outcomes</span><div className="metric-value">{verifications.length}</div><span className="metric-note">Post-action checks</span></article>
                  <article className="metric"><span className="metric-label">Recovered</span><div className="metric-value">{recovered}</div><span className="metric-note">Confirmed recovery</span></article>
                  <article className="metric"><span className="metric-label">Average confidence</span><div className="metric-value">{averageConfidence === null ? "—" : `${Math.round(averageConfidence * 100)}%`}</div><span className="metric-note">Verification confidence</span></article>
                  <article className="metric"><span className="metric-label">Feedback records</span><div className="metric-value">{feedback.length}</div><span className="metric-note">Operator signals</span></article>
                </section>
                <section className="dashboard-grid">
                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Verification outcomes</h2><span className="panel-link">Before / after metrics</span></div>
                    {verifications.map((item) => (
                      <div className="verification-row" key={item.id}>
                        <span className={item.recovered ? "recovery-mark recovered" : "recovery-mark"}>{item.recovered ? "OK" : "Review"}</span>
                        <div><strong>{item.message}</strong><span>{Math.round(item.confidence * 100)}% confidence · {item.remediation_id}</span><small>Latency {item.metrics_before.latency_p95_ms}ms → {item.metrics_after.latency_p95_ms}ms · Errors {item.metrics_before.error_rate_percent}% → {item.metrics_after.error_rate_percent}%</small></div>
                      </div>
                    ))}
                    {verifications.length === 0 && <p className="empty-state">No verification outcomes recorded.</p>}
                  </article>
                  <article className="panel panel-wide">
                    <div className="panel-header"><h2>Operator feedback</h2><span className="panel-link">Learning signals</span></div>
                    {feedback.map((item) => (
                      <div className="feedback-row" key={item.id}>
                        <div><strong>{item.useful ? "Useful" : "Needs review"}</strong><span>{item.notes || "No notes supplied."}</span><small>{item.labels.join(" · ") || "unlabeled"}</small></div>
                      </div>
                    ))}
                    {feedback.length === 0 && <p className="empty-state">No feedback recorded.</p>}
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
