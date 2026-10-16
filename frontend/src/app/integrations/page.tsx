"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ContextGuard } from "../../components/context-guard";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import {
  createCloudIntegration,
  deleteCloudIntegration,
  fetchCloudIntegrations,
  type CloudIntegrationCatalog,
  type CloudProviderId,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

const providerLabels: Record<CloudProviderId, string> = {
  aws: "Amazon Web Services",
  azure: "Microsoft Azure",
  gcp: "Google Cloud",
  kubernetes: "Kubernetes",
  openshift: "Red Hat OpenShift",
  github: "GitHub",
  "on-prem": "On-premises",
};
const providers: CloudProviderId[] = ["aws", "azure", "gcp", "kubernetes", "openshift", "github", "on-prem"];

export default function IntegrationsPage() {
  const { permissions, activeProject, activeEnvironment, isContextComplete } = useWorkspace();
  const canRead = permissions.hasPermission("cloud:read");
  const [catalog, setCatalog] = useState<CloudIntegrationCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setCatalog(await fetchCloudIntegrations(signal));
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : "Unable to load cloud integration status.");
      }
    }
  }, []);

  useEffect(() => {
    if (!isContextComplete || !canRead) return;
    const controller = new AbortController();
    void loadCatalog(controller.signal);
    return () => controller.abort();
  }, [isContextComplete, activeProject?.id, activeEnvironment?.id, loadCatalog, canRead]);

  async function addConnectionReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError(null);
    try {
      const provider = String(form.get("provider")) as CloudProviderId;
      await createCloudIntegration({
        provider,
        display_name: String(form.get("display_name") || "").trim(),
        account_id: String(form.get("account_id") || "").trim(),
        identity_reference: String(form.get("identity_reference") || "").trim(),
      });
      setShowForm(false);
      event.currentTarget.reset();
      await loadCatalog();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to save the cloud identity reference.");
    } finally {
      setSaving(false);
    }
  }

  async function removeConnection(integrationId: string, displayName: string) {
    let productionConfirmation: string | undefined;
    if (activeEnvironment?.type === "Production") {
      productionConfirmation = window.prompt(
        `Production safeguard: enter environment slug "${activeEnvironment.slug}" to remove “${displayName}”.`,
      ) ?? undefined;
      if (productionConfirmation !== activeEnvironment.slug) {
        if (productionConfirmation !== undefined) {
          setError("Production confirmation did not match the active environment slug.");
        }
        return;
      }
    } else if (!window.confirm(`Remove the unverified reference “${displayName}” from this environment?`)) {
      return;
    }
    setError(null);
    try {
      await deleteCloudIntegration(integrationId, productionConfirmation);
      await loadCatalog();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to remove this integration reference.");
    }
  }

  const canManage = permissions.hasPermission("cloud:manage");

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">Governance <strong>/ Cloud integrations</strong></span>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Cloud integrations" permission="cloud:read">
            <section className="page-heading">
              <div>
                <span className="kicker">Environment connections</span>
                <h1>Kubernetes & Cloud Integration</h1>
                <p className="lede">Manage identity references for {activeProject?.name} / {activeEnvironment?.name}.</p>
              </div>
              {canManage && (
                <button type="button" className="primary-button" onClick={() => setShowForm((open) => !open)}>
                  {showForm ? "Cancel" : "Add identity reference"}
                </button>
              )}
            </section>

            <div className="warning-panel panel" role="note">
              <strong>Not connected or verified.</strong>
              <p>
                This deployment stores identity references only. Live authentication, account discovery, and connection
                verification are not implemented here. Do not enter API keys, access tokens, passwords, or private keys.
              </p>
            </div>
            {error && <div className="error-panel panel" role="alert"><p>{error}</p></div>}

            {showForm && canManage && (
              <form className="panel create-incident-form" onSubmit={addConnectionReference}>
                <h2>Register an identity reference</h2>
                <label className="field">
                  <span>Provider</span>
                  <select name="provider" defaultValue="aws">
                    {providers.map((provider) => (
                      <option value={provider} key={provider}>{providerLabels[provider]}</option>
                    ))}
                  </select>
                </label>
                <div className="field-row">
                  <label className="field"><span>Display name</span><input name="display_name" required minLength={2} maxLength={150} /></label>
                  <label className="field"><span>Account / cluster identifier</span><input name="account_id" required maxLength={200} /></label>
                </div>
                <label className="field">
                  <span>Workload identity reference</span>
                  <input name="identity_reference" required maxLength={500} placeholder="Role ARN, managed identity, service account, or cluster context" />
                </label>
                <p className="data-note">Only an identity locator is stored. Provider credentials and verification are not accepted by this endpoint.</p>
                <button type="submit" className="primary-button" disabled={saving}>
                  {saving ? "Saving reference…" : "Save unverified reference"}
                </button>
              </form>
            )}

            {!catalog && !error && <p className="data-note" role="status">Loading provider and environment status…</p>}
            {catalog && (
              <section className="dashboard-grid">
                <article className="panel panel-wide">
                  <div className="panel-header"><h2>Provider capabilities</h2><span className="panel-link">Identity references only</span></div>
                  <div className="provider-grid">
                    {catalog.providers.map((provider) => (
                      <div className="provider-card" key={provider.provider}>
                        <strong>{providerLabels[provider.provider]}</strong>
                        <span>{provider.connection_mode}</span>
                        <small>{provider.verification_supported ? "Verification available" : "Verification not configured"}</small>
                      </div>
                    ))}
                  </div>
                </article>
                <article className="panel panel-wide">
                  <div className="panel-header"><h2>References in this environment</h2><span className="panel-link">{catalog.connections.length}</span></div>
                  {catalog.connections.map((connection) => (
                    <div className="document-row" key={connection.id}>
                      <div>
                        <strong>{connection.display_name} · {providerLabels[connection.provider]}</strong>
                        <span>{connection.account_id} · {connection.identity_reference}</span>
                        <small>Status: Unverified. {connection.status_detail}</small>
                      </div>
                      {canManage && (
                        <button type="button" className="secondary-button" onClick={() => void removeConnection(connection.id, connection.display_name)}>
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                  {catalog.connections.length === 0 && (
                    <p className="empty-state">No identity references are registered for this environment.</p>
                  )}
                </article>
              </section>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
