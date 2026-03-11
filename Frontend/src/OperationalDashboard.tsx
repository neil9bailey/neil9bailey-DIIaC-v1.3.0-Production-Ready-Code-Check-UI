import { useCallback, useEffect, useMemo, useState } from "react";
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
  onClose: () => void;
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase();
  const cls =
    s === "PASS" ? "pass" : s === "WARN" ? "warn" : s === "FAIL" ? "fail" : "unknown";
  return <span className={`status-badge ${cls}`}>{s}</span>;
}

function timeSince(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export default function OperationalDashboard({ onClose }: Props) {
  const [health, setHealth] = useState<IntegrationsHealthResponse | null>(null);
  const [trends, setTrends] = useState<TrendSummaryResponse | null>(null);
  const [config, setConfig] = useState<EffectiveConfigResponse | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [changeHistory, setChangeHistory] = useState<ConfigChangeRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState<number | null>(null);
  const [freshnessTick, setFreshnessTick] = useState(0);
  const [error, setError] = useState<string>("");
  const [authBlocked, setAuthBlocked] = useState(false);

  // Change request form
  const [crField, setCrField] = useState("");
  const [crValue, setCrValue] = useState("");
  const [crReason, setCrReason] = useState("");
  const [crStatus, setCrStatus] = useState("");

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
      setLastRefreshAt(Date.now());
      setAuthBlocked(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("no_diiac_role") || msg.includes("authentication_required") || msg.includes("401") || msg.includes("403")) {
        setAuthBlocked(true);
        setError("Dashboard access denied. Your account does not have the required DIIaC role or permissions. Contact your admin to configure role mappings.");
      } else {
        setError("Failed to load dashboard data. Ensure bridge is running.");
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const healthInterval = setInterval(() => {
      if (authBlocked) return;
      fetchIntegrationsHealth().then(setHealth).catch(() => {});
      fetchPendingApprovals().then((a) => setApprovals(a.pending || [])).catch(() => {});
    }, 30000);
    const trendInterval = setInterval(() => {
      if (authBlocked) return;
      fetchTrendSummary(24).then(setTrends).catch(() => {});
    }, 60000);
    const fullRefreshInterval = setInterval(() => {
      if (authBlocked) return;
      void refresh();
    }, 120000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(trendInterval);
      clearInterval(fullRefreshInterval);
    };
  }, [refresh, authBlocked]);

  useEffect(() => {
    if (!lastRefreshAt) return;
    const interval = setInterval(() => {
      setFreshnessTick((t) => t + 1);
    }, 5000);
    return () => clearInterval(interval);
  }, [lastRefreshAt]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  async function submitChangeRequest() {
    if (!crField.trim() || !crReason.trim()) { setCrStatus("Field and reason are required."); return; }
    try {
      setCrStatus("Submitting...");
      await submitConfigChangeRequest({ field: crField.trim(), proposed_value: crValue.trim() || undefined, reason: crReason.trim() });
      setCrStatus("Change request submitted.");
      setCrField(""); setCrValue(""); setCrReason("");
      const ch = await fetchConfigChangeHistory();
      setChangeHistory(ch.requests || []);
    } catch (err) { console.error(err); setCrStatus("Failed to submit change request."); }
  }

  const globalClass = health?.global_status === "PASS" ? "pass" : health?.global_status === "WARN" ? "warn" : "fail";
  const lastRefreshText = useMemo(() => (
    lastRefreshAt ? new Date(lastRefreshAt).toLocaleTimeString() : "..."
  ), [lastRefreshAt]);
  const freshnessText = useMemo(() => {
    if (!lastRefreshAt) return "Never";
    const ageSec = Math.floor((Date.now() - lastRefreshAt) / 1000);
    if (ageSec < 10) return "Live";
    if (ageSec < 90) return `${ageSec}s old`;
    return `Stale (${ageSec}s old)`;
  }, [lastRefreshAt, freshnessTick]);

  return (
    <div className="dashboard-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dashboard-container">
        {/* Header */}
        <div className="dashboard-header">
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <h2>DIIaC Operational Dashboard</h2>
            <span className="env-badge">PROD</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              Last refresh: {lastRefreshText}
            </span>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              Freshness: {freshnessText}
            </span>
            <button onClick={() => void refresh()} style={{ background: "rgba(255,255,255,.1)", border: "1px solid #64748b", color: "#e2e8f0", padding: "4px 12px", fontSize: 12, borderRadius: 4 }}>
              Refresh
            </button>
            <button className="dashboard-close" onClick={onClose}>x</button>
          </div>
        </div>

        <div className="dashboard-body">
          {loading && <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>Loading dashboard...</div>}
          {error && <div className="status" style={{ background: "#fef2f2", color: "#b91c1c", borderLeftColor: "#dc2626" }}>{error}</div>}

          {health && !loading && (
            <>
              {/* ── Global Status Banner ────────────────────────── */}
              <div className={`global-status-banner ${globalClass}`}>
                <span className="status-label">Global Status: {health.global_status}</span>
                <span>Critical Alerts: <strong>{health.critical_alerts}</strong></span>
                <span>Open Approvals: <strong>{health.open_approvals}</strong></span>
                <span>Drift: <strong>{health.drift}</strong></span>
              </div>

              {/* ── Integration Health Cards ────────────────────── */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Integration Health</h3>
              </div>
              <div className="health-cards-grid">
                {/* Entra Identity */}
                <div className="health-card">
                  <div className="health-card-header">
                    <span className="health-card-title">Entra Identity</span>
                    <StatusBadge status={health.entra_identity.status} />
                  </div>
                  <div className="health-card-row"><span className="label">Auth Mode</span><span className="value">{health.entra_identity.auth_mode}</span></div>
                  <div className="health-card-row"><span className="label">Tenant/Aud</span><span className="value">{health.entra_identity.tenant_id === "configured" ? "OK" : health.entra_identity.tenant_id}</span></div>
                  <div className="health-card-row"><span className="label">OIDC Discovery</span><span className="value">{health.entra_identity.oidc_discovery}</span></div>
                  <div className="health-card-row"><span className="label">Role Map</span><span className="value">{health.entra_identity.role_map_loaded ? "Loaded" : "Not loaded"}</span></div>
                  <div className="health-card-row"><span className="label">Issuer Pinning</span><span className="value">{health.entra_identity.issuer_pinning}</span></div>
                </div>

                {/* LLM Integration */}
                <div className="health-card">
                  <div className="health-card-header">
                    <span className="health-card-title">LLM Integration</span>
                    <StatusBadge status={health.llm_integration.status} />
                  </div>
                  <div className="health-card-row"><span className="label">Ingestion</span><span className="value">{health.llm_integration.ingestion_enabled ? "Enabled" : "Disabled"}</span></div>
                  <div className="health-card-row"><span className="label">API Key</span><span className="value">{health.llm_integration.api_key}</span></div>
                  <div className="health-card-row"><span className="label">Stub Mode</span><span className="value">{health.llm_integration.stub_mode ? "Enabled" : "Disabled"}</span></div>
                  <div className="health-card-row"><span className="label">Model</span><span className="value">{health.llm_integration.model}</span></div>
                </div>

                {/* Approval Ops */}
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

              {/* Runtime bar */}
              <div style={{ display: "flex", gap: 16, padding: "10px 16px", background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, marginBottom: 16, fontSize: 12, flexWrap: "wrap" }}>
                <span>Python Runtime: <StatusBadge status={health.runtime.python} /></span>
                <span>Trust Ledger: <StatusBadge status={health.runtime.trust_ledger} /></span>
                <span>DB Integrity: <StatusBadge status={health.runtime.db_integrity} /></span>
                <span>Replay Verifier: <StatusBadge status={health.runtime.replay_verifier} /></span>
              </div>

              {/* ── Governance Operations ───────────────────────── */}
              {trends && (
                <div className="governance-ops">
                  <h3>Copilot Intercept Telemetry (Optional)</h3>
                  <div style={{ marginTop: -4, marginBottom: 8, fontSize: 12, color: "#64748b" }}>
                    This panel only reflects <code>/api/intercept/*</code> workflows.
                    Standard governed compile runs do not populate these metrics.
                  </div>
                  <div className="ops-stat-row">
                    <div className="ops-stat"><span className="label">Request Intercepts ({trends.window_hours}h):</span></div>
                    <div className="ops-stat"><span className="label">ALLOW</span><span className="value">{trends.request_intercepts.allow_pct}% ({trends.request_intercepts.allow_count}/{trends.request_intercepts.total})</span></div>
                    <div className="ops-stat"><span className="label">RESTRICT</span><span className="value">{trends.request_intercepts.restrict_pct}% ({trends.request_intercepts.restrict_count}/{trends.request_intercepts.total})</span></div>
                    <div className="ops-stat"><span className="label">REQUIRE_APPROVAL</span><span className="value">{trends.request_intercepts.require_approval_pct}% ({trends.request_intercepts.require_approval_count}/{trends.request_intercepts.total})</span></div>
                  </div>
                  <div className="ops-stat-row">
                    <div className="ops-stat"><span className="label">Response Governance ({trends.window_hours}h):</span></div>
                    <div className="ops-stat"><span className="label">ALLOW</span><span className="value">{trends.response_governance.allow_pct}% ({trends.response_governance.allow_count}/{trends.response_governance.total})</span></div>
                    <div className="ops-stat"><span className="label">REMEDIATE</span><span className="value">{trends.response_governance.remediate_pct}% ({trends.response_governance.remediate_count}/{trends.response_governance.total})</span></div>
                  </div>
                  {trends.request_intercepts.total === 0 && trends.response_governance.total === 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#64748b" }}>
                      No intercept events recorded in the selected window.
                    </div>
                  )}
                  {trends.top_block_reasons.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#475569" }}>
                      <strong>Top Block Reasons:</strong> {trends.top_block_reasons.map((r) => r.reason).join(", ")}
                    </div>
                  )}
                </div>
              )}

              {/* ── Open Approval Queue ─────────────────────────── */}
              <div className="approval-section">
                <h3>Open Approval Queue</h3>
                {approvals.length === 0 ? (
                  <div style={{ color: "#64748b", fontSize: 12, padding: "8px 0" }}>No pending approvals.</div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Execution</th>
                        <th>Requested By</th>
                        <th>Age</th>
                        <th>Risk</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {approvals.map((a) => (
                        <tr key={a.approval_id}>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{a.approval_id}</td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{a.execution_id || a.intercept_id || "n/a"}</td>
                          <td>{a.requested_by}</td>
                          <td>{timeSince(a.requested_at)}</td>
                          <td><span className="status-badge warn">{a.risk_level}</span></td>
                          <td><span className="status-badge unknown">{a.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* ── Configuration (Read-only) ──────────────────── */}
              {config && (
                <div className="config-section">
                  <h3>Configuration (Read-only)</h3>
                  <div className="config-row">
                    <div className="config-item"><span className="label">Auth Mode:</span><span className="value">{config.auth.mode}</span></div>
                    <div className="config-item"><span className="label">Tenant:</span><span className="value">{config.auth.tenant_id || "n/a"}</span></div>
                    <div className="config-item"><span className="label">Audience:</span><span className="value">{config.auth.audience || "n/a"}</span></div>
                    <div className="config-item"><span className="label">Issuer Pinning:</span><span className="value">{config.auth.issuer_pinning ? "ON" : "OFF"}</span></div>
                  </div>
                  <div className="config-row" style={{ marginTop: 4 }}>
                    <div className="config-item"><span className="label">Signing:</span><span className="value">{config.signing.enabled ? "ON" : "OFF"}</span></div>
                    <div className="config-item"><span className="label">Key:</span><span className="value">{config.signing.key_id}</span></div>
                    <div className="config-item"><span className="label">Key Mode:</span><span className="value">{config.signing.key_mode}</span></div>
                    <div className="config-item"><span className="label">LLM Model:</span><span className="value">{config.llm.model}</span></div>
                  </div>
                  <div className="config-row" style={{ marginTop: 4 }}>
                    <div className="config-item"><span className="label">TLS Profiles:</span><span className="value">{config.tls.profiles_loaded} loaded</span></div>
                    <div className="config-item"><span className="label">Cert Warnings:</span><span className="value">{config.tls.cert_expiry_warnings}</span></div>
                    <div className="config-item"><span className="label">Offload:</span><span className="value">{config.offload.targets.length ? config.offload.targets.join(", ") : "none"}</span></div>
                  </div>

                  {/* Change request form */}
                  <hr />
                  <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>
                    <div>
                      <label style={{ display: "block", marginBottom: 2 }}>Config Field</label>
                      <input value={crField} onChange={(e) => setCrField(e.target.value)} placeholder="e.g. llm.model" style={{ width: 160 }} />
                    </div>
                    <div>
                      <label style={{ display: "block", marginBottom: 2 }}>Proposed Value</label>
                      <input value={crValue} onChange={(e) => setCrValue(e.target.value)} placeholder="e.g. gpt-4o" style={{ width: 140 }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <label style={{ display: "block", marginBottom: 2 }}>Reason</label>
                      <input value={crReason} onChange={(e) => setCrReason(e.target.value)} placeholder="Justification for change" style={{ width: "100%" }} />
                    </div>
                    <button onClick={() => void submitChangeRequest()} className="btn-secondary" style={{ marginBottom: 0 }}>Request Config Change</button>
                  </div>
                  {crStatus && <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{crStatus}</div>}

                  {/* Change history */}
                  {changeHistory.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <h4 style={{ fontSize: 12, color: "#64748b", margin: "0 0 6px" }}>Change History</h4>
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
        </div>
      </div>
    </div>
  );
}
