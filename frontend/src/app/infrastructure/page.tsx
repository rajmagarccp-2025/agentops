"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { fetchChanges, fetchInventory, type ChangeEvent, type InventoryResource } from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

export default function InfrastructurePage() {
  const { permissions } = useWorkspace();
  const [resources, setResources] = useState<InventoryResource[] | null>(null);
  const [changes, setChanges] = useState<ChangeEvent[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetchInventory(controller.signal), fetchChanges(controller.signal)])
      .then(([nextResources, nextChanges]) => {
        setResources(nextResources);
        setChanges(nextChanges);
      })
      .catch(() => setError(true));
    return () => controller.abort();
  }, []);

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">Operations <strong>/ SRE & Infrastructure</strong></span>
          </div>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="SRE & Infrastructure Control">
            <section className="page-heading"><div><span className="kicker">Normalized inventory</span><h1>Infrastructure Drift</h1><p className="lede">Provider-neutral resources, services, and recent operational changes.</p></div>{permissions.canAskAI() && <Link className="btn btn-primary" href="/agents?workflow=discovery">Start discovery workflow</Link>}</section>
            {error && <p className="data-note warning">Infrastructure data is unavailable. Check API authentication and readiness.</p>}
            {!error && (!resources || !changes) && <p className="data-note">Loading inventory and change intelligence...</p>}
            {resources && changes && <section className="dashboard-grid">
              <article className="panel panel-wide"><div className="panel-header"><h2>Resource inventory</h2><span className="panel-link">{resources.length} resources</span></div>{resources.map((resource) => <div className="resource-row" key={resource.resource_id}><span className="resource-kind">{resource.kind}</span><div><strong>{resource.name}</strong><span>{resource.service ?? "unassigned"} · {resource.resource_id}</span></div><small>{resource.status}</small></div>)}{resources.length === 0 && <p className="data-note">No inventory has been discovered.</p>}</article>
              <article className="panel panel-wide"><div className="panel-header"><h2>Recent changes</h2><span className="panel-link">Timeline</span></div>{changes.map((change) => <div className="change-row" key={change.id}><div><strong>{change.title}</strong><span>{change.change_type} · {change.service} · {change.environment}</span></div><small>{new Date(change.occurred_at).toLocaleString()}</small></div>)}{changes.length === 0 && <p className="data-note">No changes recorded.</p>}</article>
            </section>}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
