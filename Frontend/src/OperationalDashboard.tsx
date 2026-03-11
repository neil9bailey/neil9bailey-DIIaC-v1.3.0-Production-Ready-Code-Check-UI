import { useCallback, useEffect, useState } from "react";
import {
  fetchIntegrationsHealth,
  fetchTrendSummary,
  fetchEffectiveConfig,
  fetchPendingApprovals,
  fetchConfigChangeHistory,
  submitConfigChangeRequest,
  type IntegrationsHealthResponse,
  type TrendSummaryResponse,
  type EffectiveConfigResponse,
  type PendingApproval,
  type ConfigChangeRequest,
} from "./api";

interface Props {
  onClose?: () => void;
  /** When true, renders inline as a page instead of a modal overlay */
  inline?: boolean;
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase();
  const cls = s === "PASS" ? "pass" : s === "WARN" ? "warn" : s === "FAIL" ? "fail" : "unknown";
  return <span className={`status-badge ${cls}`}>{s}</span>;
}

function timeSince(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ago`;
}

function DashboardContent({ health, trends, config, approvals, changeHistory, loading, error, lastRefresh, onRefresh }: {
  health: IntegrationsHealthResponse | null;
  trends: TrendSummaryResponse | null;
  config: EffectiveConfigResponse | null;
  approvals: PendingApproval[];
  changeHistory: ConfigChangeRequest[];
  loading: boolean;
  error: string;
  lastRefresh: string;
  onRefresh: () => void;
}) {
  const [crField, setCrField] = useState("");
  const [crValue, setCrValue] = useState("");
  const [crReason, setCrReason] = useState("");
  const [crStatus, setCrStatus] = useState("");

  async function submitChangeRequest() {
    if (!crField.trim() || !crReason.trim()) { setCrStatus("Config field and reason are required."); return; }
    try {
      setCrStatus("Submitting…");
      await submitConfigChangeRequest({ field: crField.trim(), proposed_value: crValue.trim() || undefined, reason: crReason.trim() });
      setCrStatus("✔ Change request submitted.");
      setCrField(""); setCrValue(""); setCrReason("");
      onRefresh();
    } catch (err) { console.error(err); setCrStatus("Failed to submit change request."); }
  }

  const globalClass = health?.global_status === "PASS" ? "pass" : health?.global_status === "WARN" ? "warn" : "fail";

  return (
    <>
      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="env-badge">PROD</span>
          {lastRefresh && <span style={{ fontSize: 11, color: "var(--slate-400)" }}>Last refresh: {lastRefresh}</span>}
        </div>
        <button className="btn-secondary" onClick={onRefresh} style={{ fontSize: 12, padding: "5px 14px" }}>
          ↻ Refresh
        </button>
      </div>

      {loading && <div style={{ textAlign: "center", padding: 40, color: "var(--slate-400)" }}>Loading dashboard data…</div>}
      {error && <div className="status" style={{ background: "var(--red-50)", color: "var(--red-700)", borderLeftColor: "var(--red-600)", marginBottom: 16 }}>{error}</div>}

      {health && !loading && (
        <>
          {/* Global Status Banner */}
          <div className={`global-status-banner ${globalClass}`}>
            <span className="status-label">Global: {health.global_status}</span>
            <span>Critical Alerts: <strong>{health.critical_alerts}</strong></span>
            <span>Open Approvals: <strong>{health.open_approvals}</strong></span>
            <span>Drift: <strong>{health.drift}</strong></span>
          </div>

          {/* Runtime Bar */}
          <div style={{ display: "flex", gap: 16, padding: "10px 16px", background: "var(--white)", border: "1px solid var(--slate-200)", borderRadius: 8, marginBottom: 16, fontSize: 12, flexWrap: "wrap" }}>
            <span>Python: <StatusBadge status={health.runtime.python} /></span>
            <span>Trust Ledger: <StatusBadge status={health.runtime.trust_ledger} /></span>
            <span>DB Integrity: <StatusBadge status={health.runtime.db_integrity} /></span>
            <span>Replay Verifier: <StatusBadge status={health.runtime.replay_verifier} /></span>
          </div>

          {/* Integration Health Cards */}
          <h3 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700, color: "var(--navy-800)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Integration Health
          </h3>
          <div className="health-cards-grid">
            <div className="health-card">
              <div className="health-card-header">
                <span className="health-card-title">Entra Identity</span>
                <StatusBadge status={health.entra_identity.status} />
              </div>
              <div className="health-card-row"><span className="label">Auth Mode</span><span className="value">{health.entra_identity.auth_mode}</span></div>
              <div className="health-card-row"><span className="label">Tenant / Audience</span><span className="value">{health.entra_identity.tenant_id === "configured" ? "✔ OK" : health.entra_identity.tenant_id}</span></div>
              <div className="health-card-row"><span className="label">OIDC Discovery</span><span className="value">{health.entra_identity.oidc_discovery}</span></div>
              <div className="health-card-row"><span className="label">Role Map</span><span className="value">{health.entra_identity.role_map_loaded ? "Loaded" : "Not loaded"}</span></div>
              <div className="health-card-row"><span className="label">Issuer Pinning</span><span className="value">{health.entra_identity.issuer_pinning}</span></div>
            </div>
            <div className="health-card">
              <div className="health-card-header">
                <span className="health-card-title">LLM Integration</span>
                <StatusBadge status={health.llm_integration.status} />
              </div>
              <div className="health-card-row"><span className="label">Ingestion</span><span className="value">{health.llm_integration.ingestion_enabled ? "Enabled" : "Disabled"}</span></div>
              <div className="health-card-row"><span className="label">API Key</span><span className="value">{health.llm_integration.api_key}</span></div>
              <div className="health-card-row"><span className="label">Stub Mode</span><span className="value">{health.llm_integration.stub_mode ? "Enabled" : "Disabled"}</span></div>
              <div className="health-card-row"><span className="label">Dual LLM Loop</span><span className="value" style={{ color: health.llm_integration.dual_llm_loop ? "var(--green-600, #16a34a)" : "var(--slate-400)" }}>{health.llm_integration.dual_llm_loop ? "ACTIVE" : "INACTIVE"}</span></div>
              {health.llm_integration.providers && (
                <>
                  <div style={{ borderTop: "1px solid var(--slate-200)", margin: "8px 0 6px", paddingTop: 6, fontSize: 11, fontWeight: 700, color: "var(--navy-700)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Providers in Loop</div>
                  <div className="health-card-row">
                    <span className="label">ChatGPT</span>
                    <span className="value" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <StatusBadge status={health.llm_integration.providers.chatgpt.status} />
                      <span style={{ fontSize: 11, color: "var(--slate-500)" }}>{health.llm_integration.providers.chatgpt.model}</span>
                    </span>
                  </div>
                  <div className="health-card-row" style={{ fontSize: 11, color: "var(--slate-400)", paddingLeft: 8, marginTop: -4 }}>
                    <span>Role: {health.llm_integration.providers.chatgpt.role.replace(/_/g, " ")}</span>
                  </div>
                  <div className="health-card-row">
                    <span className="label">Copilot</span>
                    <span className="value" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <StatusBadge status={health.llm_integration.providers.copilot.status} />
                      <span style={{ fontSize: 11, color: "var(--slate-500)" }}>{health.llm_integration.providers.copilot.model}</span>
                    </span>
                  </div>
                  <div className="health-card-row" style={{ fontSize: 11, color: "var(--slate-400)", paddingLeft: 8, marginTop: -4 }}>
                    <span>Role: {health.llm_integration.providers.copilot.role.replace(/_/g, " ")}</span>
                  </div>
                </>
              )}
            </div>
            <div className="health-card">
              <div className="health-card-header">
                <span className="health-card-title">Approval Ops</span>
                <StatusBadge status={health.approval_ops.status} />
              </div>
              <div className="health-card-row"><span className="label">Pending</span><span className="value">{health.approval_ops.pending_count}</span></div>
              <div className="health-card-row"><span className="label">Persistence</span><span className="value">{health.approval_ops.persistence}</span></div>
              <div className="health-card-row"><span className="label">Last Decision SLA</span><span className="value">{health.approval_ops.last_decision_sla}</span></div>
            </div>
          </div>

          {/* Governance Operations */}
          {trends && (
            <div className="governance-ops">
              <h3>Governance Operations <span style={{ fontSize: 11, fontWeight: 400, color: "var(--slate-400)" }}>({trends.window_hours}h window)</span></h3>
              <div className="ops-stat-row">
                <span style={{ fontWeight: 600, color: "var(--navy-700)" }}>Request Intercepts:</span>
                <div className="ops-stat"><span className="label">ALLOW</span><span className="value">{trends.request_intercepts.allow_pct}%</span></div>
                <div className="ops-stat"><span className="label">RESTRICT</span><span className="value">{trends.request_intercepts.restrict_pct}%</span></div>
                <div className="ops-stat"><span className="label">REQUIRE APPROVAL</span><span className="value">{trends.request_intercepts.require_approval_pct}%</span></div>
              </div>
              <div className="ops-stat-row">
                <span style={{ fontWeight: 600, color: "var(--navy-700)" }}>Response Governance:</span>
                <div className="ops-stat"><span className="label">ALLOW</span><span className="value">{trends.response_governance.allow_pct}%</span></div>
                <div className="ops-stat"><span className="label">REMEDIATE</span><span className="value">{trends.response_governance.remediate_pct}%</span></div>
              </div>
              {trends.top_block_reasons.length > 0 && (
                <div style={{ marginTop: 10, fontSize: 12, color: "var(--slate-500)" }}>
                  <strong>Top Block Reasons:</strong> {trends.top_block_reasons.map((r) => r.reason).join(" · ")}
                </div>
              )}
            </div>
          )}

          {/* Open Approval Queue */}
          <div className="approval-section">
            <h3>
              Open Approval Queue
              {approvals.length > 0 && (
                <span style={{ marginLeft: 8, background: "var(--amber-100)", color: "var(--amber-700)", borderRadius: 999, padding: "1px 8px", fontSize: 11, fontWeight: 700 }}>
                  {approvals.length}
                </span>
              )}
            </h3>
            {approvals.length === 0 ? (
              <div style={{ color: "var(--slate-400)", fontSize: 12, padding: "8px 0" }}>✔ No pending approvals</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>ID</th><th>Execution</th><th>Requested By</th><th>Age</th><th>Risk</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {approvals.map((a) => (
                    <tr key={a.approval_id}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{a.approval_id}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{a.execution_id || a.intercept_id || "n/a"}</td>
                      <td>{a.requested_by}</td>
                      <td style={{ fontSize: 11 }}>{timeSince(a.requested_at)}</td>
                      <td><span className="status-badge warn">{a.risk_level}</span></td>
                      <td><span className="status-badge unknown">{a.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Configuration (read-only) + Change Request */}
          {config && (
            <div className="config-section">
              <h3>Effective Configuration <span style={{ fontSize: 11, fontWeight: 400, color: "var(--slate-400)" }}>(read-only)</span></h3>
              <div className="config-row">
                <div className="config-item"><span className="label">Auth Mode:</span><span className="value">{config.auth.mode}</span></div>
                <div className="config-item"><span className="label">Tenant:</span><span className="value">{config.auth.tenant_id || "n/a"}</span></div>
                <div className="config-item"><span className="label">Audience:</span><span className="value">{config.auth.audience || "n/a"}</span></div>
                <div className="config-item"><span className="label">Issuer Pinning:</span><span className="value">{config.auth.issuer_pinning ? "ON" : "OFF"}</span></div>
              </div>
              <div className="config-row" style={{ marginTop: 4 }}>
                <div className="config-item"><span className="label">Signing:</span><span className="value">{config.signing.enabled ? "ON" : "OFF"}</span></div>
                <div className="config-item"><span className="label">Key ID:</span><span className="value">{config.signing.key_id}</span></div>
                <div className="config-item"><span className="label">Key Mode:</span><span className="value">{config.signing.key_mode}</span></div>
                <div className="config-item"><span className="label">LLM Model:</span><span className="value">{config.llm.model}</span></div>
              </div>
              <div className="config-row" style={{ marginTop: 4 }}>
                <div className="config-item"><span className="label">TLS Profiles:</span><span className="value">{config.tls.profiles_loaded} loaded</span></div>
                <div className="config-item"><span className="label">Cert Warnings:</span><span className="value">{config.tls.cert_expiry_warnings}</span></div>
                <div className="config-item"><span className="label">Offload:</span><span className="value">{config.offload.targets.length ? config.offload.targets.join(", ") : "none"}</span></div>
              </div>

              <hr />
              <div style={{ marginBottom: 8, fontSize: 12, fontWeight: 700, color: "var(--navy-800)" }}>Request Config Change</div>
              <div className="form-section" style={{ margin: 0 }}>
                <div className="form-section-body">
                  <div className="form-grid-3">
                    <div className="form-field">
                      <label>Config Field</label>
                      <input value={crField} onChange={(e) => setCrField(e.target.value)} placeholder="e.g. llm.model" />
                      <div className="field-hint">Dot-notation field path</div>
                    </div>
                    <div className="form-field">
                      <label>Proposed Value</label>
                      <input value={crValue} onChange={(e) => setCrValue(e.target.value)} placeholder="e.g. gpt-4o" />
                    </div>
                    <div className="form-field">
                      <label>Justification</label>
                      <input value={crReason} onChange={(e) => setCrReason(e.target.value)} placeholder="Reason for this change request" />
                    </div>
                  </div>
                  <div className="button-row" style={{ marginTop: 10 }}>
                    <button className="btn-secondary" onClick={() => void submitChangeRequest()}>Submit Change Request</button>
                  </div>
                  {crStatus && <div style={{ fontSize: 11, color: crStatus.startsWith("✔") ? "var(--green-600)" : "var(--slate-500)", marginTop: 4 }}>{crStatus}</div>}
                </div>
              </div>

              {changeHistory.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--slate-400)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Change History</div>
                  <table>
                    <thead><tr><th>ID</th><th>Field</th><th>Status</th><th>By</th><th>When</th></tr></thead>
                    <tbody>
                      {changeHistory.slice(0, 10).map((r) => (
                        <tr key={r.request_id}>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.request_id}</td>
                          <td>{r.field}</td>
                          <td><span className={`status-badge ${r.status === "approved" ? "pass" : r.status === "rejected" ? "fail" : "unknown"}`}>{r.status}</span></td>
                          <td>{r.requested_by}</td>
                          <td style={{ fontSize: 11 }}>{r.requested_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}

export default function OperationalDashboard({ onClose, inline }: Props) {
  const [health, setHealth] = useState<IntegrationsHealthResponse | null>(null);
  const [trends, setTrends] = useState<TrendSummaryResponse | null>(null);
  const [config, setConfig] = useState<EffectiveConfigResponse | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [changeHistory, setChangeHistory] = useState<ConfigChangeRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<string>("");
  const [error, setError] = useState<string>("");

  const refresh = useCallback(async () => {
    try {
      setError("");
      const [h, t, c, a, ch] = await Promise.all([
        fetchIntegrationsHealth(),
        fetchTrendSummary(24),
        fetchEffectiveConfig(),
        fetchPendingApprovals(),
        fetchConfigChangeHistory(),
      ]);
      setHealth(h);
      setTrends(t);
      setConfig(c);
      setApprovals(a.pending || []);
      setChangeHistory(ch.requests || []);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error(err);
      setError("Failed to load dashboard data. Ensure the bridge service is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const healthInterval = setInterval(() => {
      fetchIntegrationsHealth().then(setHealth).catch(console.error);
      fetchPendingApprovals().then((a) => setApprovals(a.pending || [])).catch(console.error);
    }, 30000);
    const trendInterval = setInterval(() => {
      fetchTrendSummary(24).then(setTrends).catch(console.error);
    }, 60000);
    return () => { clearInterval(healthInterval); clearInterval(trendInterval); };
  }, [refresh]);

  useEffect(() => {
    if (inline) return; // No escape key handler for page mode
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape" && onClose) onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, inline]);

  const content = (
    <DashboardContent
      health={health}
      trends={trends}
      config={config}
      approvals={approvals}
      changeHistory={changeHistory}
      loading={loading}
      error={error}
      lastRefresh={lastRefresh}
      onRefresh={() => void refresh()}
    />
  );

  // ── Page / inline mode ────────────────────────────────────
  if (inline) {
    return <div>{content}</div>;
  }

  // ── Modal overlay mode (legacy) ───────────────────────────
  return (
    <div className="dashboard-overlay" onClick={(e) => { if (e.target === e.currentTarget && onClose) onClose(); }}>
      <div className="dashboard-container">
        <div className="dashboard-header">
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <h2>DIIaC Operational Dashboard</h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {onClose && (
              <button className="dashboard-close" onClick={onClose}>×</button>
            )}
          </div>
        </div>
        <div className="dashboard-body">{content}</div>
      </div>
    </div>
  );
}
