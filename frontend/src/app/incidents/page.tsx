"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import { createIncident, fetchIncidents, type Incident } from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

export default function IncidentsPage() {
  const { permissions } = useWorkspace();
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadIncidents = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setIncidents(await fetchIncidents(signal));
    } catch (err: unknown) {
      if (!signal?.aborted) setError(err instanceof Error ? err.message : "Unable to load incidents.");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadIncidents(controller.signal);
    return () => controller.abort();
  }, [loadIncidents]);

  async function submitIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      await createIncident({
        title: String(form.get("title") || "").trim(),
        service: String(form.get("service") || "").trim(),
        severity: String(form.get("severity") || "P3") as Incident["severity"],
        description: String(form.get("description") || "").trim(),
        started_at: new Date(String(form.get("started_at"))).toISOString(),
      });
      setShowCreateForm(false);
      event.currentTarget.reset();
      await loadIncidents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to create incident.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">Operations <strong>/ Observability & Incidents</strong></span>
          </div>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Observability & Incident Management">
            <GlobalContextSelector />
            <section className="page-heading">
              <div>
                <span className="kicker">Reliability control</span>
                <h1>Incident Management & Observability</h1>
                <p className="lede">Tenant-scoped incidents collected from operational systems.</p>
              </div>
              {permissions.hasPermission("incidents:write") && (
                <button type="button" className="primary-button" onClick={() => setShowCreateForm((open) => !open)}>
                  {showCreateForm ? "Cancel" : "Create incident"}
                </button>
              )}
            </section>
            {showCreateForm && (
              <form className="panel create-incident-form" onSubmit={submitIncident}>
                <h2>Record an incident</h2>
                <div className="field-row">
                  <label className="field"><span>Title</span><input name="title" required maxLength={300} /></label>
                  <label className="field"><span>Service</span><input name="service" required maxLength={200} /></label>
                </div>
                <div className="field-row">
                  <label className="field"><span>Severity</span><select name="severity" defaultValue="P3"><option>P1</option><option>P2</option><option>P3</option><option>P4</option></select></label>
                  <label className="field"><span>Started at</span><input name="started_at" type="datetime-local" required defaultValue={new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 16)} /></label>
                </div>
                <label className="field"><span>Description</span><textarea name="description" rows={3} maxLength={10_000} /></label>
                <button type="submit" className="primary-button" disabled={submitting}>{submitting ? "Saving…" : "Save incident"}</button>
              </form>
            )}
            <section className="panel panel-wide">
              <div className="panel-header"><h2>Current queue</h2><span className="panel-link">Live API data</span></div>
              {error && <div className="error-panel" role="alert"><p>{error}</p><button type="button" className="btn btn-secondary" onClick={() => void loadIncidents()}>Retry</button></div>}
              {!error && !incidents && <p className="data-note" role="status">Loading incident queue...</p>}
              {!error && incidents?.length === 0 && <p className="empty-state">No incidents are currently recorded.</p>}
              {incidents?.map((incident) => (
                <Link className="incident incident-link" href={`/incidents/${incident.id}`} key={incident.id}>
                  <span className={`severity ${incident.severity === "P1" ? "" : "amber"}`} />
                  <div>
                    <div className="incident-title">{incident.title}</div>
                    <div className="incident-meta">{incident.severity} / {incident.status} / {incident.service}</div>
                  </div>
                  <time className="incident-time" dateTime={incident.started_at}>{new Date(incident.started_at).toLocaleString()}</time>
                </Link>
              ))}
            </section>
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
