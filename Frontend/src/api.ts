import { authHeaders } from "./auth";

const BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:3001";

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [k: string]: JsonValue };
export type JsonObject = { [k: string]: JsonValue };

export interface GovernanceExecutionState {
  execution_id: string;
  provider: string;
  reasoning_level: string;
  policy_level: string;
  pack_hash: string;
  ledger_root: string;
  signature_present?: boolean;
  signing_enabled?: boolean;
  signing_key_id?: string;
  key_mode?: string;
}

export interface GovernanceDecisionResponse {
  execution_state: GovernanceExecutionState;
}

export interface TrustDashboardResponse {
  valid: boolean;
  records: number;
  ledger_root: string;
  frozen: boolean;
}

export interface PolicyImpactResponse {
  severity: string;
  impacted_controls: number;
  findings: number;
  evaluated_at: string;
}

export interface PolicyDiffChange {
  field: string;
}

export interface PolicyDiffResponse {
  diff: { changes: PolicyDiffChange[] };
  simulated_impact: JsonObject;
}

export interface BusinessProfileEntry {
  profile_id?: string;
  file?: string;
  allowed_schemas?: string[];
  [k: string]: JsonValue | undefined;
}

export interface BusinessProfilesResponse {
  profiles: BusinessProfileEntry[];
  profiles_count: number;
}

export interface AdminHealthResponse {
  status: string;
  signing_enabled?: boolean;
  signing_key_id?: string;
  key_mode?: string;
  strict_deterministic_mode?: boolean;
  ledger_record_count?: number;
  timestamp?: string;
}

export interface VerifyExecutionResponse {
  execution_id: string;
  status: string;
  signature_present: boolean;
  pack_hash?: string;
  merkle_root?: string;
  manifest_hash?: string;
  signature_payload_schema_version?: string;
  signing_key_id?: string;
  trust_source?: string;
}

export interface AdminMetricsResponse {
  health_status?: string;
  executions_total?: number;
  signed_recent_executions?: number;
  ledger_record_count?: number;
  routes?: Record<string, JsonObject>;
  [k: string]: JsonValue | undefined;
}

export interface AdminDbStatusResponse {
  db_path?: string;
  tables?: Record<string, number>;
  integrity?: JsonObject;
  [k: string]: JsonValue | undefined;
}

export interface ServiceStatusResponse {
  timestamp: string;
  overall_ok: boolean;
  services: JsonObject;
}

export interface ContainerStatusResponse {
  available: boolean;
  command?: string;
  error?: string;
  containers: JsonObject[];
}

export interface AuditExportResponse {
  audit_export_id: string;
  download_url: string;
  storage_path?: string;
  storage_path_relative?: string;
}

export interface AuditExportListItem {
  audit_export_id: string;
  created_at?: string;
  execution_ids?: string[];
  download_url: string;
  storage_path?: string;
  storage_path_relative?: string;
  exists?: boolean;
  size_bytes?: number;
}

export interface AuditExportListResponse {
  exports: AuditExportListItem[];
  count: number;
}

/* ═══ Dashboard-specific types ════════════════════════════════ */

export interface IntegrationsHealthResponse {
  timestamp: string;
  global_status: "PASS" | "WARN" | "FAIL";
  critical_alerts: number;
  open_approvals: number;
  drift: string;
  entra_identity: { status: string; auth_mode: string; tenant_id: string; audience: string; oidc_discovery: string; role_map_loaded: boolean; issuer_pinning: string };
  llm_integration: { status: string; ingestion_enabled: boolean; api_key: string; stub_mode: boolean; model: string };
  approval_ops: { status: string; pending_count: number; persistence: string; last_decision_sla: string };
  runtime: { python: string; trust_ledger: string; db_integrity: string; replay_verifier: string };
}

export interface TrendSummaryResponse {
  window_hours: number;
  timestamp: string;
  request_intercepts: {
    total: number;
    allow_count: number;
    allow_pct: number;
    restrict_count: number;
    restrict_pct: number;
    require_approval_count: number;
    require_approval_pct: number;
  };
  response_governance: {
    total: number;
    allow_count: number;
    allow_pct: number;
    remediate_count: number;
    remediate_pct: number;
  };
  top_block_reasons: { reason: string; count: number }[];
}

export interface EffectiveConfigResponse {
  timestamp: string;
  auth: { mode: string; entra_enabled: boolean; tenant_id: string | null; audience: string | null; issuer_pinning: boolean };
  signing: { enabled: boolean; key_id: string; key_mode: string };
  llm: { ingestion_enabled: boolean; stub_enabled: boolean; model: string; api_key_present: boolean };
  tls: { profiles_loaded: number; cert_expiry_warnings: number };
  offload: { targets: string[] };
  python_runtime: { base_url: string; autostart: boolean };
}

export interface ConfigChangeRequest {
  request_id: string;
  field: string;
  proposed_value: string | null;
  reason: string;
  status: string;
  requested_by: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision: string | null;
}

export interface PendingApproval {
  approval_id: string;
  execution_id: string | null;
  intercept_id: string | null;
  requested_by: string;
  risk_level: string;
  status: string;
  requested_at: string;
}

export interface AuthStatusResponse {
  auth_mode: string;
  entra_enabled: boolean;
  tenant_id: string | null;
  audience: string | null;
}

/* ═══ Request helper ═════════════════════════════════════════ */

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...authHeaders(),
    ...((options.headers as Record<string, string>) || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as T;
}

/* ═══ Core governance endpoints ══════════════════════════════ */

export function createHumanInput(data: JsonObject): Promise<{ saved: string }> {
  return request<{ saved: string }>("/api/human-input", { method: "POST", body: JSON.stringify(data) });
}

export function runGovernanceDecision(payload: {
  provider: string;
  reasoning_level: string;
  policy_level: string;
}): Promise<GovernanceDecisionResponse> {
  return request<{ compile?: GovernanceDecisionResponse }>("/api/llm-governed-compile", {
    method: "POST",
    body: JSON.stringify(payload),
  }).then((res) => {
    if (res.compile?.execution_state) {
      return res.compile;
    }
    throw new Error("Legacy governance response is no longer available. Use /api/llm-governed-compile output.");
  });
}

export async function listGovernedReports(executionId: string): Promise<string[]> {
  const data = await request<{ reports?: string[]; files?: string[] } | string[]>(`/executions/${encodeURIComponent(executionId)}/reports`);
  if (Array.isArray(data)) return data;
  return data.reports || data.files || [];
}

export async function downloadGovernedReport(executionId: string, file: string): Promise<void> {
  const res = await fetch(`${BASE}/executions/${encodeURIComponent(executionId)}/reports/${encodeURIComponent(file)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) { const text = await res.text(); throw new Error(text || "Download failed"); }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = file;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(url);
}

export async function exportDecisionPack(executionId: string): Promise<void> {
  const res = await fetch(`${BASE}/decision-pack/${encodeURIComponent(executionId)}/export`, { headers: authHeaders() });
  if (!res.ok) { const text = await res.text(); throw new Error(text || "Export failed"); }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `decision-pack_${executionId}.zip`;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(url);
}

export function fetchTrustDashboard(): Promise<TrustDashboardResponse> {
  return request<TrustDashboardResponse>("/trust");
}

export function runPolicyImpact(policy_level = "P1"): Promise<PolicyImpactResponse> {
  return request<PolicyImpactResponse>("/api/impact/policy", { method: "POST", body: JSON.stringify({ policy_level }) });
}

export function listBusinessProfiles(): Promise<BusinessProfilesResponse> {
  return request<BusinessProfilesResponse>("/api/business-profiles");
}

export function submitRoleInput(payload: {
  execution_context_id: string; role: string; domain: string;
  assertions: string[]; non_negotiables: string[]; risk_flags: string[]; evidence_refs: string[];
  idempotency_key?: string;
}): Promise<{ execution_context_id: string; role_count: number; stored: boolean; duplicate_ignored?: boolean; idempotency_key?: string }> {
  return request("/api/human-input/role", { method: "POST", body: JSON.stringify(payload) });
}

export function runGovernedCompile(payload: {
  execution_context_id: string; schema_id: string; profile_id: string;
  reasoning_level?: string; policy_level?: string;
}): Promise<{ execution_id?: string; execution_state?: { execution_id?: string; signature_present?: boolean; signing_enabled?: boolean } }> {
  return request("/api/governed-compile", { method: "POST", body: JSON.stringify(payload) });
}

export function runLlmGovernedCompile(payload: {
  execution_context_id?: string; schema_id: string; profile_id: string;
  reasoning_level?: string; policy_level?: string; role?: string; domain?: string;
  assertions?: string[]; evidence_refs?: string[]; governance_modes?: string[]; provider?: string; human_intent?: string;
}): Promise<{ compile?: { execution_id?: string; execution_state?: { execution_id?: string }; decision_summary?: { decision_status?: string } } }> {
  return request("/api/llm-governed-compile", { method: "POST", body: JSON.stringify(payload) });
}

/* ═══ Admin endpoints ════════════════════════════════════════ */

export function fetchAdminHealth(): Promise<AdminHealthResponse> { return request<AdminHealthResponse>("/admin/health"); }
export function fetchAdminMetrics(): Promise<AdminMetricsResponse> { return request<AdminMetricsResponse>("/admin/metrics"); }
export function fetchAdminDbStatus(): Promise<AdminDbStatusResponse> { return request<AdminDbStatusResponse>("/admin/db/status"); }
export function runDbCompact(): Promise<JsonObject> { return request<JsonObject>("/admin/db/maintenance/compact", { method: "POST", body: JSON.stringify({}) }); }
export function fetchServiceStatus(): Promise<ServiceStatusResponse> { return request<ServiceStatusResponse>("/admin/status/services"); }
export function fetchContainerStatus(): Promise<ContainerStatusResponse> { return request<ContainerStatusResponse>("/admin/status/containers"); }
export function fetchAdminLogs(source: "backend" | "ledger"): Promise<JsonObject | JsonObject[]> { return request<JsonObject | JsonObject[]>(`/admin/logs?source=${source}`); }
export function fetchExecutionLogs(executionId: string): Promise<JsonObject> { return request<JsonObject>(`/admin/executions/${encodeURIComponent(executionId)}/logs`); }
export function verifyExecution(executionId: string): Promise<VerifyExecutionResponse> { return request<VerifyExecutionResponse>(`/verify/execution/${encodeURIComponent(executionId)}`); }
export function verifyExport(executionId: string): Promise<JsonObject> { return request<JsonObject>("/verify/export", { method: "POST", body: JSON.stringify({ execution_id: executionId }) }); }
export function generateAuditExport(executionIds: string[]): Promise<AuditExportResponse> { return request<AuditExportResponse>("/admin/audit-export", { method: "POST", body: JSON.stringify({ execution_ids: executionIds }) }); }
export function downloadAuditExport(exportId: string): Promise<JsonObject> { return request<JsonObject>(`/admin/audit-export/${encodeURIComponent(exportId)}/download`); }
export async function downloadAuditExportFile(exportId: string): Promise<void> {
  const url = `${BASE}/admin/audit-export/${encodeURIComponent(exportId)}/download`;
  const res = await fetch(url, { headers: { ...authHeaders(), "Content-Type": "application/json" } });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${exportId}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}
export function listAuditExports(): Promise<AuditExportListResponse> { return request<AuditExportListResponse>("/admin/audit/exports"); }

/* ═══ Dashboard endpoints (NEW) ══════════════════════════════ */

export function fetchAuthStatus(): Promise<AuthStatusResponse> { return request<AuthStatusResponse>("/auth/status"); }

export interface AuthMeResponse {
  name: string;
  email: string | null;
  role: string | null;
  subroles: string[];
  groups: string[];
  tenant_id: string | null;
  token_type: string;
  auth_mode: string;
}

export function fetchAuthMe(): Promise<AuthMeResponse> { return request<AuthMeResponse>("/auth/me"); }
export function fetchIntegrationsHealth(): Promise<IntegrationsHealthResponse> { return request<IntegrationsHealthResponse>("/admin/integrations/health"); }
export function fetchTrendSummary(windowHours = 24): Promise<TrendSummaryResponse> { return request<TrendSummaryResponse>(`/admin/integrations/summary/trends?window=${windowHours}`); }
export function fetchEffectiveConfig(): Promise<EffectiveConfigResponse> { return request<EffectiveConfigResponse>("/admin/config/effective"); }
export function submitConfigChangeRequest(payload: { field: string; proposed_value?: string; reason: string }): Promise<ConfigChangeRequest> { return request<ConfigChangeRequest>("/admin/config/change-request", { method: "POST", body: JSON.stringify(payload) }); }
export function fetchConfigChangeHistory(): Promise<{ requests: ConfigChangeRequest[]; count: number }> { return request("/admin/config/change-history"); }
export function decideConfigChange(requestId: string, payload: { decision: "approve" | "reject"; justification?: string }): Promise<ConfigChangeRequest> { return request<ConfigChangeRequest>(`/admin/config/change-request/${encodeURIComponent(requestId)}/decision`, { method: "POST", body: JSON.stringify(payload) }); }
export function fetchPendingApprovals(): Promise<{ pending: PendingApproval[]; count: number }> { return request("/api/intercept/approval/pending"); }
export function decideApproval(approvalId: string, payload: { decision: string; justification?: string }): Promise<JsonObject> { return request("/api/intercept/approval/decide", { method: "POST", body: JSON.stringify({ approval_id: approvalId, ...payload }) }); }

/* ═══ Stubs (disabled features) ══════════════════════════════ */

export async function generateDerivedCompliance(): Promise<{ generated: boolean }> { return { generated: false }; }
export async function listDerivedReports(): Promise<string[]> { return []; }
export async function fetchDerivedReport(_u?: string): Promise<string> { void _u; return "Derived compliance generation is not enabled in this build."; }
export async function exportDerivedReport(_u?: string, _f?: "docx" | "pdf"): Promise<void> { void _u; void _f; throw new Error("Derived compliance export is not enabled in this build."); }
export async function runPolicyDiff(_c?: string, _f?: string, _t?: string): Promise<PolicyDiffResponse> {
  void _c; void _f; void _t;
  return { diff: { changes: [] }, simulated_impact: { message: "Policy diff simulation endpoint is not enabled in this build." } };
}
