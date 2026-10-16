"use client";

import { useEffect, useState } from "react";

import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { decideApproval, fetchApprovals, type ApprovalRequest } from "../../lib/api";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchApprovals(controller.signal).then(setApprovals).catch(() => setError(true));
    return () => controller.abort();
  }, []);

  async function decide(request: ApprovalRequest, decision: "approve" | "reject") {
    setBusy(request.id);
    try {
      const updated = await decideApproval(request.id, decision, `${decision}d from the operations console.`);
      setApprovals((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? current);
    } catch {
      setError(true);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span className="breadcrumb">Governance <strong>/ Approvals</strong></span>
          </div>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="Governance & Approval Gates">
            <section className="page-heading">
              <div>
                <span className="kicker">Human control point</span>
                <h1>Approval queue</h1>
                <p className="lede">Review high-risk actions before they reach infrastructure.</p>
              </div>
            </section>
            <section className="panel panel-wide">
              <div className="panel-header"><h2>Requests</h2><span className="panel-link">Policy enforced</span></div>
              {error && <p className="data-note warning">Approval data is unavailable or the request could not be completed.</p>}
              {!error && !approvals && <p className="data-note">Loading approval queue...</p>}
              {!error && approvals?.length === 0 && <p className="data-note">No approval requests are waiting.</p>}
              {approvals?.map((request) => (
                <article className="approval-row" key={request.id}>
                  <div className="approval-risk"><span className={`risk-mark ${request.risk.toLowerCase()}`} />{request.risk}</div>
                  <div className="approval-copy"><strong>{request.action}</strong><span>{request.reason}</span><small>{request.tool_name} · requested by {request.requester}</small></div>
                  <div className="approval-actions">
                    <span className={`approval-status ${request.status}`}>{request.status}</span>
                    {request.status === "pending" && <><button className="approve-button" disabled={busy === request.id} onClick={() => decide(request, "approve")}>Approve</button><button className="reject-button" disabled={busy === request.id} onClick={() => decide(request, "reject")}>Reject</button></>}
                  </div>
                </article>
              ))}
            </section>
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
