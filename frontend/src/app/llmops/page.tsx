"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Navigation } from "../../components/navigation";
import { SystemStatus } from "../../components/system-status";
import { ContextGuard } from "../../components/context-guard";
import { GlobalContextSelector } from "../../components/global-context-selector";
import {
  assignModelAdmin,
  createEvaluation,
  createModelPolicy,
  createRegisteredModel,
  deleteModelPolicy,
  deleteRegisteredModel,
  fetchEvaluations,
  fetchLLMTelemetry,
  fetchModelAdmins,
  fetchModelPolicies,
  fetchPromptVersions,
  fetchProviderHealth,
  fetchRegisteredModels,
  invokeGatewayChatCompletion,
  removeModelAdmin,
  rotateModelCredentials,
  testModelCredentials,
  type ChatCompletionResponse,
  type EvaluationResult,
  type LLMTelemetry,
  type ModelAccessPolicy,
  type ModelAdmin,
  type PromptVersion,
  type ProviderHealth,
  type RegisteredModel,
  type TestConnectionResult,
} from "../../lib/api";
import { useWorkspace } from "../../state/workspace-context";

type LLMOpsData = {
  health: ProviderHealth;
  telemetry: LLMTelemetry[];
  prompts: PromptVersion[];
  evaluations: EvaluationResult[];
  models: RegisteredModel[];
};

export default function LLMOpsPage() {
  const { currentEnv, currentProject, permissions } = useWorkspace();
  const [data, setData] = useState<LLMOpsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"registry" | "playground" | "telemetry">("registry");

  // Modals & forms state
  const [showAddModal, setShowAddModal] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);

  // Selected model for details/sharing modal
  const [selectedModel, setSelectedModel] = useState<RegisteredModel | null>(null);
  const [modelAdmins, setModelAdmins] = useState<ModelAdmin[]>([]);
  const [modelPolicies, setModelPolicies] = useState<ModelAccessPolicy[]>([]);
  const [detailTab, setDetailTab] = useState<"overview" | "rotation" | "admins" | "sharing">("overview");

  // Manage modal fields
  const [newAdminUserId, setNewAdminUserId] = useState("");
  const [newPolicyGranteeType, setNewPolicyGranteeType] = useState<"user" | "group" | "public_org">("user");
  const [newPolicyGranteeId, setNewPolicyGranteeId] = useState("");
  const [newPolicyPermission, setNewPolicyPermission] = useState<"use" | "view_metadata" | "manage_access" | "manage_model" | "view_usage">("use");
  const [newPolicyEffect, setNewPolicyEffect] = useState<"allow" | "deny">("allow");
  const [rotateKeyInput, setRotateKeyInput] = useState("");

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [providerFilter, setProviderFilter] = useState("all");

  // Gateway Playground state
  const [playgroundModelId, setPlaygroundModelId] = useState("");
  const [playgroundPrompt, setPlaygroundPrompt] = useState("Explain the multi-model LLM gateway security model in 2 sentences.");
  const [playgroundResult, setPlaygroundResult] = useState<ChatCompletionResponse | null>(null);
  const [playgroundError, setPlaygroundError] = useState<string | null>(null);
  const [playgroundExecuting, setPlaygroundExecuting] = useState(false);

  const loadData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [health, telemetry, prompts, evaluations, models] = await Promise.all([
        fetchProviderHealth(signal),
        fetchLLMTelemetry(signal),
        fetchPromptVersions(signal),
        fetchEvaluations(signal),
        fetchRegisteredModels(signal).catch(() => []),
      ]);
      setData({ health, telemetry, prompts, evaluations, models });
      if (models.length > 0 && !playgroundModelId) {
        setPlaygroundModelId(models[0].id);
      }
    } catch (err: unknown) {
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : "Unable to load LLM operations data.");
        setData(null);
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [playgroundModelId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadData(controller.signal);
    return () => controller.abort();
  }, [loadData]);

  // Load admins and policies when selecting a model
  useEffect(() => {
    if (!selectedModel) return;
    const controller = new AbortController();
    Promise.all([
      fetchModelAdmins(selectedModel.id, controller.signal).catch(() => []),
      fetchModelPolicies(selectedModel.id, controller.signal).catch(() => []),
    ]).then(([admins, policies]) => {
      setModelAdmins(admins);
      setModelPolicies(policies);
    });
    return () => controller.abort();
  }, [selectedModel]);

  // Handle Add Model Submission
  async function handleRegisterModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);

    const provider = String(form.get("provider"));
    const model_name = String(form.get("model_name")).trim();
    const display_name = String(form.get("display_name")).trim();
    const description = String(form.get("description")).trim();
    const api_key = String(form.get("api_key")).trim();
    const base_url = String(form.get("base_url")).trim() || undefined;
    const api_version = String(form.get("api_version")).trim() || undefined;
    const organization_wide = form.get("organization_wide") === "on";

    const capabilities: string[] = [];
    if (form.get("cap_chat") === "on") capabilities.push("chat");
    if (form.get("cap_embeddings") === "on") capabilities.push("embeddings");
    if (form.get("cap_tool_calling") === "on") capabilities.push("tool_calling");
    if (form.get("cap_vision") === "on") capabilities.push("vision");
    if (form.get("cap_structured_output") === "on") capabilities.push("structured_output");

    try {
      const created = await createRegisteredModel({
        provider,
        model_name,
        display_name,
        description,
        api_key,
        base_url,
        api_version,
        capabilities,
        organization_wide,
        test_connection_first: true,
      });

      setData((prev) => (prev ? { ...prev, models: [created, ...prev.models] } : prev));
      setShowAddModal(false);
      setTestResult(null);
      event.currentTarget.reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to register model.");
    } finally {
      setSubmitting(false);
    }
  }

  // Handle Test Credentials in Form
  async function handleTestConnectionInForm(formElement: HTMLFormElement) {
    const form = new FormData(formElement);
    const provider = String(form.get("provider"));
    const model_name = String(form.get("model_name")).trim();
    const api_key = String(form.get("api_key")).trim();
    const base_url = String(form.get("base_url")).trim() || undefined;

    if (!api_key) {
      setTestResult({
        success: false,
        latency_ms: 0,
        provider,
        model_name,
        message: "Please enter an API key first.",
      });
      return;
    }

    setTestingConnection(true);
    setTestResult(null);
    try {
      const res = await testModelCredentials({ provider, model_name, api_key, base_url });
      setTestResult(res);
    } catch (err: unknown) {
      setTestResult({
        success: false,
        latency_ms: 0,
        provider,
        model_name,
        message: err instanceof Error ? err.message : "Connection test failed.",
      });
    } finally {
      setTestingConnection(false);
    }
  }

  // Handle Rotate Credentials
  async function handleRotateCredentials(e: FormEvent) {
    e.preventDefault();
    if (!selectedModel || !rotateKeyInput.trim()) return;
    setSubmitting(true);
    try {
      const updated = await rotateModelCredentials(selectedModel.id, rotateKeyInput.trim());
      setSelectedModel(updated);
      setData((prev) =>
        prev
          ? {
              ...prev,
              models: prev.models.map((m) => (m.id === updated.id ? updated : m)),
            }
          : prev
      );
      setRotateKeyInput("");
      alert("Credentials rotated successfully!");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to rotate key.");
    } finally {
      setSubmitting(false);
    }
  }

  // Handle Assign Admin
  async function handleAssignAdmin(e: FormEvent) {
    e.preventDefault();
    if (!selectedModel || !newAdminUserId.trim()) return;
    try {
      const admin = await assignModelAdmin(selectedModel.id, newAdminUserId.trim());
      setModelAdmins((prev) => [...prev, admin]);
      setNewAdminUserId("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to assign admin.");
    }
  }

  // Handle Remove Admin
  async function handleRemoveAdmin(userId: string) {
    if (!selectedModel) return;
    try {
      await removeModelAdmin(selectedModel.id, userId);
      setModelAdmins((prev) => prev.filter((a) => a.user_id !== userId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to remove admin.");
    }
  }

  // Handle Add Policy
  async function handleCreatePolicy(e: FormEvent) {
    e.preventDefault();
    if (!selectedModel) return;
    try {
      const policy = await createModelPolicy(selectedModel.id, {
        grantee_type: newPolicyGranteeType,
        grantee_id: newPolicyGranteeType === "public_org" ? null : newPolicyGranteeId.trim(),
        permission: newPolicyPermission,
        effect: newPolicyEffect,
      });
      setModelPolicies((prev) => [...prev, policy]);
      setNewPolicyGranteeId("");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to add access policy.");
    }
  }

  // Handle Delete Policy
  async function handleDeletePolicy(policyId: string) {
    if (!selectedModel) return;
    try {
      await deleteModelPolicy(selectedModel.id, policyId);
      setModelPolicies((prev) => prev.filter((p) => p.id !== policyId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to revoke policy.");
    }
  }

  // Handle Delete Model
  async function handleDeleteModel(modelId: string) {
    if (!confirm("Are you sure you want to archive this model?")) return;
    try {
      await deleteRegisteredModel(modelId);
      setData((prev) => (prev ? { ...prev, models: prev.models.filter((m) => m.id !== modelId) } : prev));
      if (selectedModel?.id === modelId) setSelectedModel(null);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete model.");
    }
  }

  // Handle Gateway Playground Test
  async function handleExecutePlayground(e: FormEvent) {
    e.preventDefault();
    if (!playgroundModelId) return;
    setPlaygroundExecuting(true);
    setPlaygroundError(null);
    setPlaygroundResult(null);

    try {
      const res = await invokeGatewayChatCompletion({
        model: playgroundModelId,
        messages: [{ role: "user", content: playgroundPrompt }],
        project_id: currentProject?.id,
        environment_id: currentEnv?.id,
      });
      setPlaygroundResult(res);
    } catch (err: unknown) {
      setPlaygroundError(err instanceof Error ? err.message : "Gateway invocation failed.");
    } finally {
      setPlaygroundExecuting(false);
    }
  }

  async function submitEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);
    try {
      const result = await createEvaluation({
        dataset: String(form.get("dataset") || "").trim(),
        model: String(form.get("model") || "").trim(),
        input_text: String(form.get("input_text") || "").trim(),
        output_text: String(form.get("output_text") || "").trim(),
        expected_text: String(form.get("expected_text") || "").trim(),
        grounded: form.get("grounded") === "on",
        tool_call_correct: form.get("tool_call_correct") === "on",
        retrieval_quality: Number(form.get("retrieval_quality")),
        latency_ms: Number(form.get("latency_ms")),
        estimated_cost_usd: Number(form.get("estimated_cost_usd")),
      });
      setData((current) => (current ? { ...current, evaluations: [result, ...current.evaluations] } : current));
      setShowForm(false);
      event.currentTarget.reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to score sample.");
    } finally {
      setSubmitting(false);
    }
  }

  const filteredModels = data?.models.filter((m) => {
    const matchesSearch =
      m.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.model_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.provider.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesProvider = providerFilter === "all" || m.provider === providerFilter;
    return matchesSearch && matchesProvider;
  }) || [];

  const averageLatency = data?.telemetry.length
    ? data.telemetry.reduce((sum, event) => sum + event.latency_ms, 0) / data.telemetry.length
    : null;
  const successRate = data?.evaluations.length
    ? data.evaluations.filter((evaluation) => evaluation.success).length / data.evaluations.length
    : null;
  const totalCost = data?.telemetry.reduce((sum, event) => sum + event.estimated_cost_usd, 0) ?? 0;

  return (
    <div className="shell">
      <Navigation />
      <div className="main">
        <header className="topbar">
          <span className="breadcrumb">
            Operations <strong>/ LLM Gateway & Multi-Model Control</strong>
          </span>
          <div className="topbar-actions">
            <SystemStatus />
          </div>
        </header>

        <main className="main-content">
          <ContextGuard featureName="LLM gateway and model operations">
            <GlobalContextSelector />

            <section className="page-heading">
              <div>
                <span className="kicker">Multi-Model LLM Gateway</span>
                <h1>LLMOps Gateway & Model Observability</h1>
                <p className="lede">
                  Register LLM models, manage secret credentials, enforce granular user/group policies, and route secure inference.
                </p>
              </div>
              <div className="action-row">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => setShowAddModal(true)}
                >
                  + Register New Model
                </button>
                {permissions.hasPermission("llm:evaluate") && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowForm((open) => !open)}
                  >
                    {showForm ? "Cancel" : "Score sample"}
                  </button>
                )}
              </div>
            </section>

            {/* Navigation Sub-Tabs */}
            <div className="tab-bar">
              <button
                type="button"
                className={`tab-item ${activeTab === "registry" ? "active" : ""}`}
                onClick={() => setActiveTab("registry")}
              >
                Model Registry ({data?.models.length ?? 0})
              </button>
              <button
                type="button"
                className={`tab-item ${activeTab === "playground" ? "active" : ""}`}
                onClick={() => setActiveTab("playground")}
              >
                Gateway Playground (POST /v1/chat/completions)
              </button>
              <button
                type="button"
                className={`tab-item ${activeTab === "telemetry" ? "active" : ""}`}
                onClick={() => setActiveTab("telemetry")}
              >
                Observability & Telemetry
              </button>
            </div>

            {error && (
              <section className="panel error-panel" role="alert">
                <p>{error}</p>
                <button type="button" className="btn btn-secondary" onClick={() => void loadData()}>
                  Retry
                </button>
              </section>
            )}

            {/* SCORE EVALUATION FORM */}
            {showForm && (
              <form className="panel create-incident-form" onSubmit={submitEvaluation}>
                <h2>Score an evaluation sample</h2>
                <div className="field-row">
                  <label className="field">
                    <span>Dataset</span>
                    <input name="dataset" required maxLength={200} />
                  </label>
                  <label className="field">
                    <span>Model or alias</span>
                    <input name="model" required maxLength={150} />
                  </label>
                </div>
                <label className="field">
                  <span>Input</span>
                  <textarea name="input_text" required maxLength={20000} rows={3} />
                </label>
                <label className="field">
                  <span>Model output</span>
                  <textarea name="output_text" required maxLength={100000} rows={4} />
                </label>
                <label className="field">
                  <span>Expected reference output</span>
                  <textarea name="expected_text" required maxLength={100000} rows={4} />
                </label>
                <div className="field-row">
                  <label className="field">
                    <span>Retrieval quality (0–1)</span>
                    <input name="retrieval_quality" type="number" min="0" max="1" step="0.01" required />
                  </label>
                  <label className="field">
                    <span>Observed latency (ms)</span>
                    <input name="latency_ms" type="number" min="0" step="1" required />
                  </label>
                </div>
                <label className="field">
                  <span>Estimated cost (USD)</span>
                  <input name="estimated_cost_usd" type="number" min="0" step="0.000001" required />
                </label>
                <label className="check-field">
                  <input name="grounded" type="checkbox" /> Grounding has been verified
                </label>
                <label className="check-field">
                  <input name="tool_call_correct" type="checkbox" /> Tool calls have been verified
                </label>
                <button type="submit" className="primary-button" disabled={submitting}>
                  {submitting ? "Scoring…" : "Save evaluation result"}
                </button>
              </form>
            )}

            {loading && <p className="data-note" role="status">Loading LLM Registry and Gateway data…</p>}

            {/* TAB 1: MODEL REGISTRY & GOVERNANCE */}
            {!loading && activeTab === "registry" && (
              <div className="registry-container">
                <div className="filter-bar">
                  <input
                    type="search"
                    placeholder="Search by model name or provider…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="search-input"
                  />
                  <select
                    value={providerFilter}
                    onChange={(e) => setProviderFilter(e.target.value)}
                    className="select-input"
                  >
                    <option value="all">All Providers</option>
                    <option value="openai">OpenAI</option>
                    <option value="azure_openai">Azure OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google_gemini">Google Gemini</option>
                    <option value="aws_bedrock">AWS Bedrock</option>
                    <option value="custom_openai">Custom OpenAI</option>
                    <option value="mock">Mock Provider</option>
                  </select>
                </div>

                <div className="panel panel-wide overflow-x-auto">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Model / Display Name</th>
                        <th>Provider</th>
                        <th>Status</th>
                        <th>Capabilities</th>
                        <th>Credentials</th>
                        <th>Permissions & Scope</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredModels.map((m) => (
                        <tr key={m.id}>
                          <td>
                            <div className="font-semibold text-white">{m.display_name}</div>
                            <div className="text-xs text-muted-gray">{m.model_name}</div>
                            {m.is_administrator && (
                              <span className="badge badge-admin mt-1">Model Administrator</span>
                            )}
                          </td>
                          <td>
                            <span className={`provider-badge provider-${m.provider}`}>
                              {m.provider}
                            </span>
                          </td>
                          <td>
                            <span className={`status-badge status-${m.status}`}>
                              {m.status}
                            </span>
                          </td>
                          <td>
                            <div className="tag-container">
                              {m.capabilities.map((cap) => (
                                <span key={cap} className="tag-chip">{cap}</span>
                              ))}
                            </div>
                          </td>
                          <td>
                            <span className="credential-pill">
                              🔐 {m.credential_status} ({m.credential_masked})
                            </span>
                          </td>
                          <td>
                            <div className="text-xs">
                              <div><strong>Scope:</strong> {m.project_ids.length > 0 ? `${m.project_ids.length} project(s)` : "Org-wide"}</div>
                              <div className="text-muted-gray">
                                {m.effective_permissions.join(", ") || "No access"}
                              </div>
                            </div>
                          </td>
                          <td>
                            <div className="action-buttons">
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => {
                                  setSelectedModel(m);
                                  setDetailTab("overview");
                                }}
                              >
                                Manage / Share
                              </button>
                              {m.is_administrator && (
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  onClick={() => void handleDeleteModel(m.id)}
                                >
                                  Archive
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                      {filteredModels.length === 0 && (
                        <tr>
                          <td colSpan={7} className="empty-state">
                            No registered models found matching filters. Click &quot;+ Register New Model&quot; to add one.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 2: UNIFIED GATEWAY PLAYGROUND */}
            {!loading && activeTab === "playground" && (
              <div className="playground-container">
                <form className="panel" onSubmit={handleExecutePlayground}>
                  <h2>Interactive LLM Gateway Invocation</h2>
                  <p className="data-note">
                    Test the unified endpoint <code>POST /v1/chat/completions</code>. Every request enforces mandatory server-side identity & scope authorization.
                  </p>

                  <div className="field-row">
                    <label className="field">
                      <span>Select Target Model</span>
                      <select
                        value={playgroundModelId}
                        onChange={(e) => setPlaygroundModelId(e.target.value)}
                        required
                      >
                        {data?.models.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.display_name} ({m.provider} - {m.model_name})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Scope Environment</span>
                      <input type="text" value={currentEnv?.name ?? "Development"} disabled />
                    </label>
                  </div>

                  <label className="field"><span>User Prompt</span>
                    <textarea
                      value={playgroundPrompt}
                      onChange={(e) => setPlaygroundPrompt(e.target.value)}
                      rows={4}
                      required
                    />
                  </label>

                  <button
                    type="submit"
                    className="primary-button"
                    disabled={playgroundExecuting}
                  >
                    {playgroundExecuting ? "Invoking Gateway…" : "Invoke Gateway (/v1/chat/completions)"}
                  </button>
                </form>

                {playgroundError && (
                  <div className="panel error-panel role-alert">
                    <h3>Authorization / Gateway Rejection (HTTP 403 / 401)</h3>
                    <p>{playgroundError}</p>
                  </div>
                )}

                {playgroundResult && (
                  <div className="panel result-panel">
                    <h3>Gateway Completion Response</h3>
                    <div className="metrics-row">
                      <span>Provider: <strong>{playgroundResult.provider}</strong></span>
                      <span>Latency: <strong>{playgroundResult.latency_ms}ms</strong></span>
                      <span>Total Tokens: <strong>{playgroundResult.usage.total_tokens}</strong></span>
                      <span>Est. Cost: <strong>${playgroundResult.estimated_cost_usd.toFixed(6)}</strong></span>
                    </div>

                    <div className="completion-content">
                      <h4>Model Output:</h4>
                      <p>{playgroundResult.choices[0]?.message.content}</p>
                    </div>

                    <details className="raw-json">
                      <summary>View Raw Normalized Gateway Payload</summary>
                      <pre>{JSON.stringify(playgroundResult, null, 2)}</pre>
                    </details>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: OBSERVABILITY & TELEMETRY */}
            {!loading && activeTab === "telemetry" && data && (
              <>
                <section className="metrics" aria-label="LLMOps summary">
                  <article className="metric">
                    <span className="metric-label">Provider health entries</span>
                    <div className="metric-value">{Object.keys(data.health.providers).length}</div>
                    <span className="metric-note">Configured catalog</span>
                  </article>
                  <article className="metric">
                    <span className="metric-label">Average latency</span>
                    <div className="metric-value">
                      {averageLatency === null ? "—" : `${Math.round(averageLatency)}ms`}
                    </div>
                    <span className="metric-note">{data.telemetry.length} telemetry samples</span>
                  </article>
                  <article className="metric">
                    <span className="metric-label">Tracked cost</span>
                    <div className="metric-value">${totalCost.toFixed(4)}</div>
                    <span className="metric-note">Recorded completions</span>
                  </article>
                  <article className="metric">
                    <span className="metric-label">Evaluation success</span>
                    <div className="metric-value">
                      {successRate === null ? "—" : `${Math.round(successRate * 100)}%`}
                    </div>
                    <span className="metric-note">{data.evaluations.length} recorded evaluations</span>
                  </article>
                </section>

                <section className="dashboard-grid">
                  <article className="panel panel-wide">
                    <div className="panel-header">
                      <h2>Provider health</h2>
                      <span className="panel-link">Gateway catalog</span>
                    </div>
                    {Object.entries(data.health.providers).map(([provider, status]) => (
                      <div className="model-row" key={provider}>
                        <span>{provider}</span>
                        <strong>{status}</strong>
                      </div>
                    ))}
                  </article>

                  <article className="panel panel-wide">
                    <div className="panel-header">
                      <h2>Prompt versions</h2>
                      <span className="panel-link">Governed templates</span>
                    </div>
                    {data.prompts.map((prompt) => (
                      <div className="model-row" key={prompt.id}>
                        <span>{prompt.name}</span>
                        <strong>v{prompt.version}</strong>
                      </div>
                    ))}
                  </article>
                </section>
              </>
            )}

            {/* MODAL 1: REGISTER MODEL DIALOG */}
            {showAddModal && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <div className="modal-header">
                    <h2>Register LLM Model</h2>
                    <button
                      type="button"
                      className="close-btn"
                      onClick={() => {
                        setShowAddModal(false);
                        setTestResult(null);
                      }}
                    >
                      ✕
                    </button>
                  </div>

                  <form onSubmit={handleRegisterModel} id="register-model-form">
                    <div className="field-row">
                      <label className="field">
                        <span>Provider</span>
                        <select name="provider" required>
                          <option value="openai">OpenAI</option>
                          <option value="azure_openai">Azure OpenAI</option>
                          <option value="anthropic">Anthropic Claude</option>
                          <option value="google_gemini">Google Gemini</option>
                          <option value="aws_bedrock">AWS Bedrock</option>
                          <option value="custom_openai">Custom OpenAI Endpoint</option>
                          <option value="mock">Mock Provider</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Model Identifier (ID)</span>
                        <input name="model_name" placeholder="e.g. gpt-4o, claude-3-5-sonnet" required />
                      </label>
                    </div>

                    <div className="field-row">
                      <label className="field">
                        <span>Display Name</span>
                        <input name="display_name" placeholder="e.g. Primary Production Reasoning Model" required />
                      </label>
                      <label className="field">
                        <span>Base URL (Optional)</span>
                        <input name="base_url" placeholder="https://api.openai.com/v1" />
                      </label>
                    </div>

                    <label className="field">
                      <span>Description</span>
                      <textarea name="description" rows={2} placeholder="Describe business use case or domain guidelines…" />
                    </label>

                    <label className="field">
                      <span>API Key / Secret Credentials</span>
                      <input
                        type="password"
                        name="api_key"
                        placeholder="sk-..."
                        required
                      />
                      <span className="field-note">
                        🔒 Plaintext key is encrypted in transit and stored in Secrets Manager. It will never be displayed again.
                      </span>
                    </label>

                    <div className="capabilities-section">
                      <span className="field-label">Supported Capabilities</span>
                      <div className="checkbox-grid">
                        <label className="check-field"><input name="cap_chat" type="checkbox" defaultChecked /> Chat / Completions</label>
                        <label className="check-field"><input name="cap_structured_output" type="checkbox" defaultChecked /> Structured JSON Output</label>
                        <label className="check-field"><input name="cap_tool_calling" type="checkbox" defaultChecked /> Tool Calling / Function Use</label>
                        <label className="check-field"><input name="cap_vision" type="checkbox" /> Vision / Multimodal</label>
                        <label className="check-field"><input name="cap_embeddings" type="checkbox" /> Embeddings</label>
                      </div>
                    </div>

                    <label className="check-field mt-2">
                      <input name="organization_wide" type="checkbox" defaultChecked /> Enable for entire organization by default
                    </label>

                    {testResult && (
                      <div className={`test-feedback ${testResult.success ? "success" : "failure"}`}>
                        {testResult.success ? "✅ Connection Verified: " : "❌ Connection Failed: "}
                        {testResult.message} ({testResult.latency_ms}ms)
                      </div>
                    )}

                    <div className="modal-actions">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={testingConnection}
                        onClick={(e) => {
                          const form = e.currentTarget.closest("form");
                          if (form) void handleTestConnectionInForm(form);
                        }}
                      >
                        {testingConnection ? "Testing…" : "Test Connection"}
                      </button>
                      <button type="submit" className="primary-button" disabled={submitting}>
                        {submitting ? "Registering…" : "Register & Activate Model"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* MODAL 2: MANAGE MODEL & SHARE ACCESS */}
            {selectedModel && (
              <div className="modal-overlay">
                <div className="modal-content modal-large">
                  <div className="modal-header">
                    <div>
                      <h2>{selectedModel.display_name}</h2>
                      <span className="text-xs text-muted-gray">{selectedModel.provider} · {selectedModel.model_name}</span>
                    </div>
                    <button type="button" className="close-btn" onClick={() => setSelectedModel(null)}>✕</button>
                  </div>

                  <div className="tab-bar modal-tabs">
                    <button
                      type="button"
                      className={`tab-item ${detailTab === "overview" ? "active" : ""}`}
                      onClick={() => setDetailTab("overview")}
                    >
                      Overview & Scopes
                    </button>
                    <button
                      type="button"
                      className={`tab-item ${detailTab === "rotation" ? "active" : ""}`}
                      onClick={() => setDetailTab("rotation")}
                    >
                      Credential Rotation
                    </button>
                    <button
                      type="button"
                      className={`tab-item ${detailTab === "admins" ? "active" : ""}`}
                      onClick={() => setDetailTab("admins")}
                    >
                      Model Administrators ({modelAdmins.length})
                    </button>
                    <button
                      type="button"
                      className={`tab-item ${detailTab === "sharing" ? "active" : ""}`}
                      onClick={() => setDetailTab("sharing")}
                    >
                      Access Policies ({modelPolicies.length})
                    </button>
                  </div>

                  <div className="modal-body">
                    {detailTab === "overview" && (
                      <div className="space-y-4">
                        <div className="info-grid">
                          <div><strong>Status:</strong> {selectedModel.status}</div>
                          <div><strong>Created By:</strong> {selectedModel.created_by}</div>
                          <div><strong>Created At:</strong> {new Date(selectedModel.created_at).toLocaleString()}</div>
                          <div><strong>Credential:</strong> 🔒 {selectedModel.credential_status} ({selectedModel.credential_masked})</div>
                        </div>
                        <div>
                          <strong>Capabilities:</strong>
                          <div className="tag-container mt-1">
                            {selectedModel.capabilities.map((c) => <span key={c} className="tag-chip">{c}</span>)}
                          </div>
                        </div>
                      </div>
                    )}

                    {detailTab === "rotation" && (
                      <form onSubmit={handleRotateCredentials} className="space-y-4">
                        <p className="text-sm">
                          Replace the provider API key in Secrets Manager. The existing value will be safely superseded without exposing it.
                        </p>
                        <label className="field">
                          <span>New API Key</span>
                          <input
                            type="password"
                            value={rotateKeyInput}
                            onChange={(e) => setRotateKeyInput(e.target.value)}
                            placeholder="sk-..."
                            required
                          />
                        </label>
                        <button type="submit" className="primary-button" disabled={submitting}>
                          {submitting ? "Rotating Key…" : "Rotate Credentials"}
                        </button>
                      </form>
                    )}

                    {detailTab === "admins" && (
                      <div className="space-y-4">
                        <form onSubmit={handleAssignAdmin} className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Enter user ID or email to add as admin..."
                            value={newAdminUserId}
                            onChange={(e) => setNewAdminUserId(e.target.value)}
                            className="search-input flex-1"
                            required
                          />
                          <button type="submit" className="btn btn-secondary">+ Add Admin</button>
                        </form>

                        <div className="admin-list space-y-2">
                          {modelAdmins.map((a) => (
                            <div key={a.id} className="flex justify-between items-center p-2 bg-dark-surface rounded">
                              <div>
                                <strong>{a.user_id}</strong>
                                <div className="text-xs text-muted-gray">Assigned by {a.assigned_by}</div>
                              </div>
                              {modelAdmins.length > 1 && (
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  onClick={() => void handleRemoveAdmin(a.user_id)}
                                >
                                  Remove
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {detailTab === "sharing" && (
                      <div className="space-y-4">
                        <form onSubmit={handleCreatePolicy} className="policy-form space-y-2">
                          <h4>Grant / Restrict Access Policy</h4>
                          <div className="field-row">
                            <label className="field"><span>Grantee Type</span>
                              <select
                                value={newPolicyGranteeType}
                                onChange={(e) => setNewPolicyGranteeType(e.target.value as "user" | "group" | "public_org")}
                              >
                                <option value="user">Specific User</option>
                                <option value="group">User Group</option>
                                <option value="public_org">Public Organization-wide</option>
                              </select>
                            </label>

                            {newPolicyGranteeType !== "public_org" && (
                              <label className="field"><span>Grantee ID</span>
                                <input
                                  type="text"
                                  placeholder={newPolicyGranteeType === "user" ? "user-id / email" : "group-slug"}
                                  value={newPolicyGranteeId}
                                  onChange={(e) => setNewPolicyGranteeId(e.target.value)}
                                  required
                                />
                              </label>
                            )}
                          </div>

                          <div className="field-row">
                            <label className="field"><span>Permission</span>
                              <select
                                value={newPolicyPermission}
                                onChange={(e) => setNewPolicyPermission(e.target.value as "use" | "view_metadata" | "manage_access" | "manage_model" | "view_usage")}
                              >
                                <option value="use">Use Model (Invoke Gateway)</option>
                                <option value="view_metadata">View Metadata</option>
                                <option value="manage_access">Manage Access Policies</option>
                                <option value="manage_model">Manage Configuration</option>
                                <option value="view_usage">View Usage & Metrics</option>
                              </select>
                            </label>

                            <label className="field"><span>Effect</span>
                              <select
                                value={newPolicyEffect}
                                onChange={(e) => setNewPolicyEffect(e.target.value as "allow" | "deny")}
                              >
                                <option value="allow">ALLOW</option>
                                <option value="deny">EXPLICIT DENY (Overrides Allow)</option>
                              </select>
                            </label>
                          </div>

                          <button type="submit" className="primary-button btn-sm">Add Policy Rule</button>
                        </form>

                        <div className="policy-list">
                          <h4>Active Policy Rules</h4>
                          {modelPolicies.map((p) => (
                            <div key={p.id} className="model-row">
                              <div>
                                <span className={`effect-badge effect-${p.effect}`}>
                                  {p.effect.toUpperCase()}
                                </span>
                                <strong> {p.permission}</strong> to {p.grantee_type} {p.grantee_id ? `(${p.grantee_id})` : "(All Organization)"}
                              </div>
                              <button
                                type="button"
                                className="btn btn-danger btn-sm"
                                onClick={() => void handleDeletePolicy(p.id)}
                              >
                                Revoke Rule
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </ContextGuard>
        </main>
      </div>
    </div>
  );
}
