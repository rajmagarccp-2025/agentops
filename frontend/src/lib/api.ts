export type HealthResponse = {
  status: "ok" | "degraded" | "error";
  service: string;
  version: string;
};

export type FinOpsSummary = {
  total_cost_usd: number;
  cost_by_service: Record<string, number>;
  utilization_records: number;
  anomaly_count: number;
  forecast_next_month_usd: number;
  recommendations: Array<{ title: string; estimated_monthly_savings_usd: number }>;
};

export type CostRecordCreate = {
  period: string;
  provider: string;
  account: string;
  service: string;
  environment: string;
  amount_usd: number;
};

export type CostRecord = CostRecordCreate & { id: string; tenant_id: string };

export type InventoryResource = {
  resource_id: string;
  kind: string;
  name: string;
  service: string | null;
  status: string;
};

export type LLMTelemetry = {
  request_id: string;
  provider: string;
  model: string;
  estimated_cost_usd: number;
  latency_ms: number;
  fallback_used: boolean;
  task: string;
  input_tokens: number;
  output_tokens: number;
  retries: number;
};

export type ObservabilityMetrics = {
  scope: "process";
  snapshot_at: string;
  metrics: Record<string, number>;
};

export function fetchObservabilityMetrics(signal?: AbortSignal): Promise<ObservabilityMetrics> {
  return getJson<ObservabilityMetrics>("/observability/metrics", signal);
}

export type Incident = {
  id: string;
  tenant_id: string;
  title: string;
  service: string;
  severity: "P1" | "P2" | "P3" | "P4";
  status: "open" | "investigating" | "resolved";
  description: string;
  started_at: string;
  created_at: string;
};

export type ApprovalRequest = {
  id: string;
  action: string;
  tool_name: string;
  reason: string;
  risk: string;
  status: "pending" | "approved" | "rejected" | "expired" | "executed";
  affected_resources: string[];
  requester: string;
  created_at: string;
  expires_at: string;
};

export type FinOpsRecommendation = {
  id: string;
  recommendation_type: string;
  service: string;
  title: string;
  rationale: string;
  estimated_monthly_savings_usd: number;
  confidence: number;
  requires_approval: boolean;
};

export type ProviderHealth = { providers: Record<string, string> };
export type PromptVersion = { id: string; name: string; version: string; template: string; created_at: string };
export type EvaluationResult = {
  id: string;
  dataset: string;
  model: string;
  correctness: number;
  groundedness: number;
  retrieval_quality: number;
  tool_call_correctness: number;
  latency_ms: number;
  estimated_cost_usd: number;
  success: boolean;
};

export type EvaluationCreate = {
  dataset: string;
  model: string;
  input_text: string;
  output_text: string;
  expected_text?: string;
  grounded: boolean;
  tool_call_correct: boolean;
  retrieval_quality: number;
  latency_ms: number;
  estimated_cost_usd: number;
};

export type RagDocument = {
  id: string;
  project_id: string | null;
  workspace_project_id: string | null;
  workspace_environment_id: string | null;
  environment_id: string | null;
  scope: "environment" | "project" | "unassigned";
  ingestion_status: "indexed";
  source: string;
  title: string;
  document_type: string;
  service: string | null;
  environment: string | null;
  tags: string[];
  allowed_roles: string[];
  created_at: string;
};

export type DocumentCreate = {
  source: string;
  title: string;
  content: string;
  document_type: "runbook" | "postmortem" | "policy" | "architecture" | "ticket" | "cloud_documentation";
  scope: "environment" | "project";
};

export type CloudProviderId = "aws" | "azure" | "gcp" | "kubernetes" | "openshift" | "github" | "on-prem";
export type CloudIntegration = {
  id: string;
  provider: CloudProviderId;
  display_name: string;
  account_id: string;
  identity_reference: string;
  status: "unverified" | string;
  status_detail: string;
  created_at: string;
};
export type CloudProviderCapability = {
  provider: CloudProviderId;
  connection_mode: string;
  verification_supported: boolean;
};
export type CloudIntegrationCatalog = {
  providers: CloudProviderCapability[];
  connections: CloudIntegration[];
};
export type CloudIntegrationCreate = {
  provider: CloudProviderId;
  display_name: string;
  account_id: string;
  identity_reference: string;
};

export function fetchCloudIntegrations(signal?: AbortSignal): Promise<CloudIntegrationCatalog> {
  return getJson<CloudIntegrationCatalog>("/cloud-integrations", signal);
}

export function createCloudIntegration(
  body: CloudIntegrationCreate,
  signal?: AbortSignal,
): Promise<CloudIntegration> {
  return postJson<CloudIntegration>("/cloud-integrations", body, signal);
}

export function deleteCloudIntegration(
  integrationId: string,
  confirmation?: string,
  signal?: AbortSignal,
): Promise<void> {
  return requestJson<void>(`/cloud-integrations/${encodeURIComponent(integrationId)}`, {
    method: "DELETE",
    signal,
    headers: confirmation
      ? { "X-Confirm-Production-Environment": confirmation }
      : undefined,
  });
}

export type ChangeEvent = {
  id: string;
  service: string;
  environment: string;
  change_type: string;
  title: string;
  occurred_at: string;
  source: string;
  actor: string | null;
};

export type SecurityFinding = {
  event_id: string;
  title: string;
  severity: number;
  confidence: number;
  evidence: Record<string, unknown>;
  recommended_action: string;
  requires_approval: boolean;
};

export type SecurityInvestigation = {
  tenant_id: string;
  findings: SecurityFinding[];
  event_count: number;
  highest_severity: number;
};

export type LearningRecord = {
  id: string;
  remediation_id: string;
  useful: boolean;
  notes: string;
  labels: string[];
  created_at: string;
};

export type LearningFeedbackCreate = {
  remediation_id: string;
  useful: boolean;
  notes: string;
  labels: string[];
};

export function createLearningFeedback(body: LearningFeedbackCreate, signal?: AbortSignal): Promise<LearningRecord> {
  return postJson<LearningRecord>("/learning/feedback", body, signal);
}

export type RetrievalResult = {
  query: string;
  context: string;
  citations: Array<{ chunk_id: string; document_id: string; title: string; source: string; excerpt: string; score: number }>;
};

export type InvestigationResponse = {
  incident: {
    incident: Incident;
    timeline: Array<{ timestamp: string; event_type: string; title: string; source: string; evidence: Record<string, unknown> }>;
    evidence: Array<{ source: string; type: string; data: Record<string, unknown> }>;
    hypotheses: string[];
    confidence: number;
    recommended_steps: string[];
  };
  run_id: string;
  status: string;
  findings: string[];
  recommendation: string | null;
  steps: Array<Record<string, unknown>>;
};

const apiBaseUrl =
  typeof window !== "undefined"
    ? "/api/proxy"
    : process.env.INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health", signal);
}

async function responseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; error?: unknown; message?: unknown };
    const detail = payload.detail ?? payload.error ?? payload.message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item
            ? String(item.msg)
            : typeof item === "string"
              ? item
              : JSON.stringify(item),
        )
        .join("; ");
    }
  } catch {
    // Some upstream errors do not include a JSON body.
  }
  return `API request failed with status ${response.status}`;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    signal,
    headers: { Accept: "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await responseError(response));
  }

  return (await response.json()) as T;
}

export function fetchFinOpsSummary(signal?: AbortSignal): Promise<FinOpsSummary> {
  return getJson<FinOpsSummary>("/finops/summary", signal);
}

export function ingestCostRecord(body: CostRecordCreate, signal?: AbortSignal): Promise<CostRecord> {
  return postJson<CostRecord>("/finops/costs", body, signal);
}

export function fetchFinOpsRecommendations(signal?: AbortSignal): Promise<FinOpsRecommendation[]> {
  return getJson<FinOpsRecommendation[]>("/finops/recommendations", signal);
}

export function fetchInventory(signal?: AbortSignal): Promise<InventoryResource[]> {
  return getJson<InventoryResource[]>("/inventory/resources", signal);
}

export function fetchChanges(signal?: AbortSignal): Promise<ChangeEvent[]> {
  return getJson<ChangeEvent[]>("/changes", signal);
}

export function fetchSecurityInvestigation(signal?: AbortSignal): Promise<SecurityInvestigation> {
  return postJson<SecurityInvestigation>("/security/investigations", {}, signal);
}

export function fetchLearningFeedback(signal?: AbortSignal): Promise<LearningRecord[]> {
  return getJson<LearningRecord[]>("/learning/feedback", signal);
}

export type VerificationResult = {
  id: string;
  remediation_id: string;
  recovered: boolean;
  confidence: number;
  metrics_before: Record<string, number>;
  metrics_after: Record<string, number>;
  deltas: Record<string, number>;
  message: string;
  verified_at: string;
};

export function fetchVerifications(signal?: AbortSignal): Promise<VerificationResult[]> {
  return getJson<VerificationResult[]>("/learning/verifications", signal);
}

export type RegisteredModel = {
  id: string;
  tenant_id: string;
  provider: string;
  model_name: string;
  display_name: string;
  description: string;
  tags: string[];
  capabilities: string[];
  status: "active" | "disabled" | "archived";
  base_url?: string | null;
  api_version?: string | null;
  provider_config: Record<string, unknown>;
  credential_status: string;
  credential_masked: string;
  created_by: string;
  is_administrator: boolean;
  effective_permissions: string[];
  project_ids: string[];
  environment_ids: string[];
  created_at: string;
  updated_at: string;
};

export type RegisteredModelCreate = {
  provider: string;
  model_name: string;
  display_name: string;
  description?: string;
  api_key: string;
  base_url?: string;
  api_version?: string;
  tags?: string[];
  capabilities?: string[];
  provider_config?: Record<string, unknown>;
  project_ids?: string[];
  environment_ids?: string[];
  organization_wide?: boolean;
  test_connection_first?: boolean;
};

export type ModelAdmin = {
  id: string;
  model_id: string;
  user_id: string;
  assigned_by: string;
  created_at: string;
};

export type ModelAccessPolicy = {
  id: string;
  model_id: string;
  organization_id: string;
  project_id?: string | null;
  environment_id?: string | null;
  grantee_type: "user" | "group" | "public_org";
  grantee_id?: string | null;
  permission: "use" | "view_metadata" | "manage_access" | "manage_model" | "view_usage";
  effect: "allow" | "deny";
  created_by: string;
  created_at: string;
};

export type TestConnectionResult = {
  success: boolean;
  latency_ms: number;
  provider: string;
  model_name: string;
  message: string;
};

export type ChatCompletionResponse = {
  id: string;
  object: string;
  created: number;
  model: string;
  provider: string;
  choices: Array<{
    index: number;
    message: { role: string; content: string };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  estimated_cost_usd: number;
  latency_ms: number;
};

export function fetchLLMTelemetry(signal?: AbortSignal): Promise<LLMTelemetry[]> {
  return getJson<LLMTelemetry[]>("/llmops/telemetry", signal);
}

export function fetchProviderHealth(signal?: AbortSignal): Promise<ProviderHealth> {
  return getJson<ProviderHealth>("/llmops/models", signal);
}

export function fetchRegisteredModels(signal?: AbortSignal): Promise<RegisteredModel[]> {
  return getJson<RegisteredModel[]>("/llmops/models", signal);
}

export function createRegisteredModel(body: RegisteredModelCreate, signal?: AbortSignal): Promise<RegisteredModel> {
  return postJson<RegisteredModel>("/llmops/models", body, signal);
}

export function updateRegisteredModel(modelId: string, body: Partial<RegisteredModelCreate>, signal?: AbortSignal): Promise<RegisteredModel> {
  return patchJson<RegisteredModel>(`/llmops/models/${encodeURIComponent(modelId)}`, body, signal);
}

export function deleteRegisteredModel(modelId: string, signal?: AbortSignal): Promise<void> {
  return requestJson<void>(`/llmops/models/${encodeURIComponent(modelId)}`, { method: "DELETE", signal });
}

export function rotateModelCredentials(modelId: string, apiKey: string, signal?: AbortSignal): Promise<RegisteredModel> {
  return postJson<RegisteredModel>(`/llmops/models/${encodeURIComponent(modelId)}/credentials`, { api_key: apiKey, test_connection: true }, signal);
}

export function testModelCredentials(body: { provider: string; model_name: string; api_key: string; base_url?: string; api_version?: string }, signal?: AbortSignal): Promise<TestConnectionResult> {
  return postJson<TestConnectionResult>("/llmops/models/test-credentials", body, signal);
}

export function fetchModelAdmins(modelId: string, signal?: AbortSignal): Promise<ModelAdmin[]> {
  return getJson<ModelAdmin[]>(`/llmops/models/${encodeURIComponent(modelId)}/admins`, signal);
}

export function assignModelAdmin(modelId: string, userId: string, signal?: AbortSignal): Promise<ModelAdmin> {
  return postJson<ModelAdmin>(`/llmops/models/${encodeURIComponent(modelId)}/admins`, { user_id: userId }, signal);
}

export function removeModelAdmin(modelId: string, userId: string, signal?: AbortSignal): Promise<void> {
  return requestJson<void>(`/llmops/models/${encodeURIComponent(modelId)}/admins/${encodeURIComponent(userId)}`, { method: "DELETE", signal });
}

export function fetchModelPolicies(modelId: string, signal?: AbortSignal): Promise<ModelAccessPolicy[]> {
  return getJson<ModelAccessPolicy[]>(`/llmops/models/${encodeURIComponent(modelId)}/policies`, signal);
}

export function createModelPolicy(modelId: string, body: Omit<ModelAccessPolicy, "id" | "model_id" | "organization_id" | "created_by" | "created_at">, signal?: AbortSignal): Promise<ModelAccessPolicy> {
  return postJson<ModelAccessPolicy>(`/llmops/models/${encodeURIComponent(modelId)}/policies`, body, signal);
}

export function deleteModelPolicy(modelId: string, policyId: string, signal?: AbortSignal): Promise<void> {
  return requestJson<void>(`/llmops/models/${encodeURIComponent(modelId)}/policies/${encodeURIComponent(policyId)}`, { method: "DELETE", signal });
}

export function invokeGatewayChatCompletion(body: { model: string; messages: Array<{ role: string; content: string }>; project_id?: string; environment_id?: string; response_format?: string }, signal?: AbortSignal): Promise<ChatCompletionResponse> {
  return postJson<ChatCompletionResponse>("/v1/chat/completions", body, signal);
}

export function fetchPromptVersions(signal?: AbortSignal): Promise<PromptVersion[]> {
  return getJson<PromptVersion[]>("/llmops/prompts", signal);
}

export function fetchEvaluations(signal?: AbortSignal): Promise<EvaluationResult[]> {
  return getJson<EvaluationResult[]>("/llmops/evaluations", signal);
}

export function createEvaluation(body: EvaluationCreate, signal?: AbortSignal): Promise<EvaluationResult> {
  return postJson<EvaluationResult>("/llmops/evaluations", body, signal);
}

export function fetchRagDocuments(signal?: AbortSignal): Promise<RagDocument[]> {
  return getJson<RagDocument[]>("/rag/documents", signal);
}

export function createKnowledgeDocument(body: DocumentCreate, signal?: AbortSignal): Promise<RagDocument> {
  return postJson<RagDocument>("/rag/documents", body, signal);
}

export function assignKnowledgeScope(
  documentId: string,
  scope: "environment" | "project",
  signal?: AbortSignal,
): Promise<RagDocument> {
  return patchJson<RagDocument>(`/rag/documents/${encodeURIComponent(documentId)}/scope`, { scope }, signal);
}

export function deleteKnowledgeDocument(
  documentId: string,
  confirmation?: string,
  signal?: AbortSignal,
): Promise<void> {
  return requestJson<void>(`/rag/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    signal,
    headers: confirmation
      ? { "X-Confirm-Production-Environment": confirmation }
      : undefined,
  });
}

export type AgentRunRequest = {
  request: string;
  request_type: "discovery" | "sre" | "investigation" | "change" | "finops" | "security" | "mlops" | "llmops" | "remediation" | "governance";
  cloud_provider: string;
  environment: string;
  target_resource: string;
  project_id?: string;
  workspace_project_id?: string | null;
  workspace_environment_id?: string | null;
};

export type AgentRunResponse = {
  run_id: string;
  status: string;
  request_type: AgentRunRequest["request_type"];
  approval_required: boolean;
  approval_id: string | null;
  findings: string[];
  recommendation: string | null;
  recommendations: string[];
  evidence: Array<Record<string, unknown>>;
  steps: Array<Record<string, unknown>>;
  error: string | null;
  confidence: number | null;
  missing_evidence: string[];
};

export type AgentRunListItem = {
  run_id: string;
  status: string;
  request_type: AgentRunRequest["request_type"];
  project_id: string | null;
  workspace_project_id: string | null;
  workspace_environment_id: string | null;
  environment: string | null;
  target_resource: string | null;
  error: string | null;
  updated_at: string;
};

export function runAgent(body: AgentRunRequest, signal?: AbortSignal): Promise<AgentRunResponse> {
  return postJson<AgentRunResponse>("/agent-runs", body, signal);
}

export function fetchAgentRuns(signal?: AbortSignal): Promise<AgentRunListItem[]> {
  return getJson<AgentRunListItem[]>("/agent-runs", signal);
}

export function fetchAgentRun(runId: string, signal?: AbortSignal): Promise<AgentRunResponse> {
  return getJson<AgentRunResponse>(`/agent-runs/${encodeURIComponent(runId)}`, signal);
}

export type IncidentCreate = {
  title: string;
  service: string;
  severity: Incident["severity"];
  started_at: string;
  description: string;
};

export function createIncident(body: IncidentCreate, signal?: AbortSignal): Promise<Incident> {
  return postJson<Incident>("/incidents", body, signal);
}

export function retrieveKnowledge(query: string, signal?: AbortSignal): Promise<RetrievalResult> {
  return postJson<RetrievalResult>("/rag/retrieve", { query, limit: 5 }, signal);
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    signal,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as T;
}

export async function patchJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, {
    method: "PATCH",
    signal,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fetchIncidents(signal?: AbortSignal): Promise<Incident[]> {
  return getJson<Incident[]>("/incidents", signal);
}

export function investigateIncident(incidentId: string, signal?: AbortSignal): Promise<InvestigationResponse> {
  return postJson<InvestigationResponse>(`/incidents/${incidentId}/investigate`, {}, signal);
}

export function fetchApprovals(signal?: AbortSignal): Promise<ApprovalRequest[]> {
  return getJson<ApprovalRequest[]>("/approvals", signal);
}

export async function decideApproval(
  requestId: string,
  decision: "approve" | "reject",
  reason: string,
): Promise<ApprovalRequest> {
  const response = await fetch(`${apiBaseUrl}/approvals/${requestId}/${decision}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: JSON.stringify({ reason }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await responseError(response));
  return (await response.json()) as ApprovalRequest;
}
