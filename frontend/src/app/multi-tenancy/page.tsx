"use client";

import React from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { HierarchyViewer } from "../../components/hierarchy-viewer";
import { GlobalContextSelector } from "../../components/global-context-selector";

export default function MultiTenancyPage() {
  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">
            Enterprise <strong>/ Multi-Tenancy Hierarchy</strong>
          </span>
          <div className="topbar-actions">
            <SystemStatus />
          </div>
        </header>
        <main className="main-content" style={{ padding: "32px 24px" }}>
          <GlobalContextSelector />
          <section className="page-heading" style={{ marginBottom: "24px" }}>
            <div>
              <span className="kicker" style={{ color: "#34d399", letterSpacing: "0.1em" }}>ENTERPRISE MULTI-TENANCY</span>
              <h1>Cryptographic Multi-Tenancy Hierarchy</h1>
              <p className="lede">
                Explore the live zero-trust tenant hierarchy showing Organization scopes, active users, assigned roles, project workspaces, environments, and autonomous AI agents.
              </p>
            </div>
          </section>

          <HierarchyViewer />
        </main>
      </div>
    </div>
  );
}
