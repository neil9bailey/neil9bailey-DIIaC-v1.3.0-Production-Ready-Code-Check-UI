const BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:3001";

type Role = "customer" | "admin";

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
}

function currentRole(): Role {
  const r = (localStorage.getItem("role") || "customer").toLowerCase();
  return r === "admin" ? "admin" : "customer";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const role = currentRole();

  const headers: Record<string, string> = {
    "x-role": role,
    ...((options.headers as Record<string, string>) || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as T;
}

export function createHumanInput(data: JsonObject): Promise<{ saved: string }> {
  return request<{ saved: string }>("/api/human-input", { method: "POST", body: JSON.stringify(data) });
}

export function runGovernanceDecision(payload: {
  provider: string;
  reasoning_level: string;
  policy_level: string;
}): Promise<GovernanceDecisionResponse> {
  return request<GovernanceDecisionResponse>("/govern/decision", { method: "POST", body: JSON.stringify(payload) });
}

export async function listGovernedReports(executionId: string): Promise<string[]> {
  const data = await request<{ reports?: string[]; files?: string[] } | string[]>(`/executions/${encodeURIComponent(executionId)}/reports`);
  if (Array.isArray(data)) return data;
  return data.reports || data.files || [];
}

export async function downloadGovernedReport(executionId: string, file: string): Promise<void> {
  const role = currentRole();
  const res = await fetch(`${BASE}/executions/${encodeURIComponent(executionId)}/reports/${encodeURIComponent(file)}`, {
    headers: { "x-role": role },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Download failed");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function exportDecisionPack(executionId: string): Promise<void> {
  const role = currentRole();
  const res = await fetch(`${BASE}/decision-pack/${encodeURIComponent(executionId)}/export`, { headers: { "x-role": role } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Export failed");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `decision-pack_${executionId}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
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
  execution_context_id: string;
  role: string;
  domain: string;
  assertions: string[];
  non_negotiables: string[];
  risk_flags: string[];
  evidence_refs: string[];
}): Promise<{ execution_context_id: string; role_count: number; stored: boolean }> {
  return request("/api/human-input/role", { method: "POST", body: JSON.stringify(payload) });
}

export function runGovernedCompile(payload: {
  execution_context_id: string;
  schema_id: string;
  profile_id: string;
  reasoning_level?: string;
  policy_level?: string;
}): Promise<{ execution_id?: string; execution_state?: { execution_id?: string; signature_present?: boolean; signing_enabled?: boolean } }> {
  return request("/api/governed-compile", { method: "POST", body: JSON.stringify(payload) });
}

export function fetchAdminHealth(): Promise<AdminHealthResponse> {
  return request<AdminHealthResponse>("/admin/health");
}


export function fetchAdminMetrics(): Promise<AdminMetricsResponse> {
  return request<AdminMetricsResponse>("/admin/metrics");
}

export function fetchAdminDbStatus(): Promise<AdminDbStatusResponse> {
  return request<AdminDbStatusResponse>("/admin/db/status");
}

export function runDbCompact(): Promise<JsonObject> {
  return request<JsonObject>("/admin/db/maintenance/compact", { method: "POST", body: JSON.stringify({}) });
}

export function fetchServiceStatus(): Promise<ServiceStatusResponse> {
  return request<ServiceStatusResponse>("/admin/status/services");
}

export function fetchContainerStatus(): Promise<ContainerStatusResponse> {
  return request<ContainerStatusResponse>("/admin/status/containers");
}

export function fetchAdminLogs(source: "backend" | "ledger"): Promise<JsonObject | JsonObject[]> {
  return request<JsonObject | JsonObject[]>(`/admin/logs?source=${source}`);
}

export function fetchExecutionLogs(executionId: string): Promise<JsonObject> {
  return request<JsonObject>(`/admin/executions/${encodeURIComponent(executionId)}/logs`);
}

export function verifyExecution(executionId: string): Promise<VerifyExecutionResponse> {
  return request<VerifyExecutionResponse>(`/verify/execution/${encodeURIComponent(executionId)}`);
}

export function generateAuditExport(executionIds: string[]): Promise<AuditExportResponse> {
  return request<AuditExportResponse>("/admin/audit-export", { method: "POST", body: JSON.stringify({ execution_ids: executionIds }) });
}

export function downloadAuditExport(exportId: string): Promise<JsonObject> {
  return request<JsonObject>(`/admin/audit-export/${encodeURIComponent(exportId)}/download`);
}

export async function generateDerivedCompliance(): Promise<{ generated: boolean }> {
  return { generated: false };
}

export async function listDerivedReports(): Promise<string[]> {
  return [];
}

export async function fetchDerivedReport(_unusedFile?: string): Promise<string> {
  void _unusedFile;
  return "Derived compliance generation is not enabled in this build.";
}

export async function exportDerivedReport(_unusedFile?: string, _unusedFormat?: "docx" | "pdf"): Promise<void> {
  void _unusedFile;
  void _unusedFormat;
  throw new Error("Derived compliance export is not enabled in this build.");
}

export async function runPolicyDiff(
  _unusedContract?: string,
  _unusedFromVersion?: string,
  _unusedToVersion?: string,
): Promise<PolicyDiffResponse> {
  void _unusedContract;
  void _unusedFromVersion;
  void _unusedToVersion;
  return {
    diff: { changes: [] },
    simulated_impact: { message: "Policy diff simulation endpoint is not enabled in this build." },
  };
}
