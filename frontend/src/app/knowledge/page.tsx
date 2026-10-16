"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import {
  assignKnowledgeScope,
  createKnowledgeDocument,
  deleteKnowledgeDocument,
  fetchRagDocuments,
  retrieveKnowledge,
  type RagDocument,
  type RetrievalResult,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

const documentTypes = ["runbook", "postmortem", "policy", "architecture", "ticket", "cloud_documentation"] as const;

export default function KnowledgePage() {
  const { permissions, activeProject, activeEnvironment } = useWorkspace();
  const canReadKnowledge = permissions.hasPermission("rag:read");
  const [documents, setDocuments] = useState<RagDocument[] | null>(null);
  const [retrieval, setRetrieval] = useState<RetrievalResult | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [updatingDocumentId, setUpdatingDocumentId] = useState<string | null>(null);

  const loadDocuments = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setDocuments(await fetchRagDocuments(signal));
    } catch (err: unknown) {
      if (!signal?.aborted) setError(err instanceof Error ? err.message : "Unable to load knowledge documents.");
    }
  }, []);

  async function assignLegacyDocument(document: RagDocument) {
    setUpdatingDocumentId(document.id);
    setError(null);
    try {
      await assignKnowledgeScope(document.id, "environment");
      await loadDocuments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to assign the document to this environment.");
    } finally {
      setUpdatingDocumentId(null);
    }
  }

  async function removeDocument(document: RagDocument) {
    let productionConfirmation: string | undefined;
    if (activeEnvironment?.type === "Production") {
      productionConfirmation = window.prompt(
        `Production safeguard: enter environment slug "${activeEnvironment.slug}" to permanently remove “${document.title}”.`,
      ) ?? undefined;
      if (productionConfirmation !== activeEnvironment.slug) {
        if (productionConfirmation !== undefined) {
          setError("Production confirmation did not match the active environment slug.");
        }
        return;
      }
    } else if (!window.confirm(`Remove “${document.title}” and its indexed passages? This cannot be undone.`)) {
      return;
    }
    setUpdatingDocumentId(document.id);
    setError(null);
    try {
      await deleteKnowledgeDocument(document.id, productionConfirmation);
      await loadDocuments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to remove this document.");
    } finally {
      setUpdatingDocumentId(null);
    }
  }

  useEffect(() => {
    if (!canReadKnowledge) return;
    const controller = new AbortController();
    void loadDocuments(controller.signal);
    return () => controller.abort();
  }, [loadDocuments, activeProject?.id, activeEnvironment?.id, canReadKnowledge]);

  async function search(event: FormEvent) {
    event.preventDefault();
    setSearching(true);
    setError(null);
    setRetrieval(null);
    try {
      setRetrieval(await retrieveKnowledge(query.trim()));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Knowledge retrieval failed.");
    } finally {
      setSearching(false);
    }
  }

  async function ingest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError(null);
    try {
      const selectedType = documentTypes.find((type) => type === form.get("document_type"));
      if (!selectedType) throw new Error("Select a supported document type.");
      await createKnowledgeDocument({
        title: String(form.get("title") || "").trim(),
        source: String(form.get("source") || "").trim(),
        content: String(form.get("content") || "").trim(),
        document_type: selectedType,
        scope: form.get("scope") === "project" ? "project" : "environment",
      });
      setShowIngest(false);
      event.currentTarget.reset();
      await loadDocuments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to ingest this document.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">Governance <strong>/ Knowledge</strong></span>
          <div className="topbar-actions"><SystemStatus /></div>
        </header>
        <main className="main-content">
          <ContextGuard featureName="RAG and knowledge" permission="rag:read">
            <GlobalContextSelector />
            <section className="page-heading">
              <div>
                <span className="kicker">Evidence library</span>
                <h1>RAG Knowledge Base & Runbooks</h1>
                <p className="lede">Search access-aware runbooks, postmortems, policies, and architecture records.</p>
              </div>
              {permissions.hasPermission("rag:write") && (
                <button type="button" className="primary-button" onClick={() => setShowIngest((open) => !open)}>
                  {showIngest ? "Cancel" : "Ingest document"}
                </button>
              )}
            </section>
            <p className="data-note" role="status">
              Scope: <strong>{activeProject?.name}</strong> / <strong>{activeEnvironment?.name}</strong>.
              Project-wide documents are shared only within this project; legacy unassigned documents are excluded from search until assigned.
            </p>

            {error && <div className="error-panel panel" role="alert"><p>{error}</p></div>}

            {showIngest && (
              <form className="panel create-incident-form" onSubmit={ingest}>
                <h2>Ingest a knowledge document</h2>
                <div className="field-row">
                  <label className="field"><span>Title</span><input name="title" required maxLength={300} /></label>
                  <label className="field"><span>Source</span><input name="source" required maxLength={500} placeholder="Document URL or internal reference" /></label>
                </div>
                <label className="field">
                  <span>Document type</span>
                  <select name="document_type" defaultValue="runbook">
                    <option value="runbook">Runbook</option>
                    <option value="postmortem">Postmortem</option>
                    <option value="policy">Policy</option>
                    <option value="architecture">Architecture</option>
                    <option value="ticket">Ticket</option>
                    <option value="cloud_documentation">Cloud documentation</option>
                  </select>
                </label>
                <label className="field">
                  <span>Knowledge scope</span>
                  <select name="scope" defaultValue="environment">
                    <option value="environment">Selected environment only ({activeEnvironment?.name})</option>
                    <option value="project">Project-wide (all environments in this project)</option>
                  </select>
                </label>
                <label className="field"><span>Content</span><textarea name="content" required maxLength={1_000_000} rows={8} /></label>
                <button type="submit" className="primary-button" disabled={saving || !permissions.hasPermission("rag:write")}>
                  {saving ? "Indexing document…" : "Index document"}
                </button>
                <p className="data-note">Indexing runs synchronously. This form stores supplied text; it does not crawl URLs or connect external repositories.</p>
              </form>
            )}

            <form className="knowledge-search" onSubmit={search}>
              <input aria-label="Search knowledge" value={query} onChange={(event) => setQuery(event.target.value)} required placeholder="Ask a question or search your indexed documents" />
              <button className="primary-button" type="submit" disabled={searching || !query.trim()}>
                {searching ? "Searching…" : "Retrieve context"}
              </button>
            </form>

            <section className="dashboard-grid">
              <article className="panel panel-wide" id="documents">
                <div className="panel-header"><h2>Documents</h2><span className="panel-link">Access filtered</span></div>
                {!documents && !error && <p className="data-note" role="status">Loading knowledge catalog…</p>}
                {!documents && error && <button type="button" className="secondary-button" onClick={() => void loadDocuments()}>Retry loading documents</button>}
                {documents?.map((document) => (
                  <div className="document-row" key={document.id}>
                    <div>
                      <strong>{document.title}</strong>
                      <span>{document.document_type} · {document.service ?? "No service"} · {document.scope === "environment" ? activeEnvironment?.name : document.scope === "project" ? `${activeProject?.name} · all environments` : "Legacy · unassigned"}</span>
                      <small>{document.ingestion_status === "indexed" ? "Indexed" : document.ingestion_status}</small>
                    </div>
                    <div className="document-actions">
                      <small>{document.allowed_roles.length ? document.allowed_roles.join(", ") : "all roles"}</small>
                      {document.scope === "unassigned" && permissions.hasPermission("rag:write") && (
                        <button type="button" className="secondary-button" disabled={updatingDocumentId === document.id} onClick={() => void assignLegacyDocument(document)}>
                          {updatingDocumentId === document.id ? "Assigning…" : "Assign to this environment"}
                        </button>
                      )}
                      {permissions.hasPermission("rag:write") && (
                        <button type="button" className="secondary-button" disabled={updatingDocumentId === document.id} onClick={() => void removeDocument(document)}>
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {documents?.length === 0 && <p className="empty-state">No accessible documents are indexed yet.</p>}
              </article>
              <article className="panel panel-wide" id="retrieval" aria-live="polite">
                <div className="panel-header"><h2>Retrieved context</h2><span className="panel-link">Cited results</span></div>
                {searching && <p className="data-note" role="status">Retrieving authorized context…</p>}
                {!retrieval && !searching && <p className="empty-state">Submit a search to view citations and retrieved context.</p>}
                {retrieval?.citations.map((citation) => (
                  <div className="citation-row" key={citation.chunk_id}>
                    <strong>{citation.title}</strong><span>{citation.source} · score {citation.score.toFixed(3)}</span><p>{citation.excerpt}</p>
                  </div>
                ))}
                {retrieval && retrieval.citations.length === 0 && <p className="empty-state">No accessible passages matched this query.</p>}
                {retrieval && <p className="data-note">Results are limited to this environment and project-wide documents. Unassigned legacy documents are not searched.</p>}
              </article>
            </section>
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
