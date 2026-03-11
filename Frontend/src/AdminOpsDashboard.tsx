import { useCallback, useEffect, useState } from "react";
import {
  decideConfigChange,
  fetchConfigChangeHistory,
  fetchEffectiveConfig,
  fetchIntegrationsHealth,
  fetchPendingApprovals,
  fetchTrendSummary,
  submitConfigChangeRequest,
  verifyReplay,
  verifyReplayBatch,
  type ConfigChangeRequest,
  type EffectiveConfigResponse,
  type IntegrationsHealthResponse,
  type JsonObject,
  type PendingApproval,
  type TrendSummaryResponse,
  type VerifyReplayResponse,
} from "./api";

interface Props {
  role: string;
  onClose: () => void;
}

function pretty(v: unknown): string {
  return JSON.stringify(v, null, 2);
}

export default function AdminOpsDashboard({ role, onClose }: Props) {
  const [status, setStatus] = useState("");
  const [showRaw, setShowRaw] = useState(false);

  // Integration health
  const [health, setHealth] = useState<IntegrationsHealthResponse | null>(null);
  const [trends, setTrends] = useState<TrendSummaryResponse | null>(null);
  const [config, setConfig] = useState<EffectiveConfigResponse | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [changeHistory, setChangeHistory] = useState<ConfigChangeRequest[]>([]);

  // Config change request
  const [configField, setConfigField] = useState("trust_mode");
  const [configValue, setConfigValue] = useState("strict");
  const [configReason, setConfigReason] = useState("");

  // Replay attestation
  const [replayExecutionId, setReplayExecutionId] = useState("");
  const [replayBatchIds, setReplayBatchIds] = useState("[]");
  const [replayResult, setReplayResult] = useState<VerifyReplayResponse | null>(null);

  const loadIntegrationOps = useCallback(async () => {
    try {
      setStatus("Loading ops dashboard...");
      const [h, t, c, a, ch] = await Promise.all([
        fetchIntegrationsHealth(),
        fetchTrendSummary(24),
        fetchEffectiveConfig(),
        fetchPendingApprovals().then((r) => r.pending ?? []),
        fetchConfigChangeHistory().then((r) => r.requests ?? []),
      ]);
      setHealth(h);
      setTrends(t);
      setConfig(c);
      setApprovals(a);
      setChangeHistory(ch);
      setStatus("Dashboard loaded.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to load ops dashboard.");
    }
  }, []);

  useEffect(() => {
    if (role !== "admin") return;
    void loadIntegrationOps();
  }, [role, loadIntegrationOps]);

  async function handleSubmitConfigChange() {
    try {
      const field = configField.trim();
      const reason = configReason.trim();
      if (!field || !reason) {
        setStatus("Field and reason are required for a config change request.");
        return;
      }
      setStatus("Submitting config change request...");
      await submitConfigChangeRequest({ field, proposed_value: configValue.trim() || undefined, reason });
      setStatus("Config change request submitted.");
      void loadIntegrationOps();
    } catch (err: unknown) {
      console.error(err);
      setStatus("Config change request failed.");
    }
  }

  async function handleDecideChange(requestId: string, decision: "approve" | "reject") {
    try {
      setStatus(`${decision === "approve" ? "Approving" : "Rejecting"} request ${requestId}...`);
      await decideConfigChange(requestId, { decision });
      setStatus(`Request ${requestId} ${decision}d.`);
      void loadIntegrationOps();
    } catch (err: unknown) {
      console.error(err);
      setStatus("Decision failed.");
    }
  }

  async function runReplayAttestation() {
    try {
      const id = replayExecutionId.trim();
      if (!id) {
        setStatus("Replay requires an execution_id.");
        return;
      }
      setStatus("Running deterministic replay attestation...");
      const result = await verifyReplay({ execution_id: id });
      setReplayResult(result);
      const ok =
        result.replay_valid === true ||
        String(result.status ?? "").toUpperCase() === "VERIFIED";
      setStatus(
        ok
          ? "Replay attestation VERIFIED."
          : "Replay attestation returned non-verified status.",
      );
    } catch (err: unknown) {
      console.error(err);
      setReplayResult({ status: "FAILED" });
      setStatus("Replay attestation FAILED (deployment should be blocked).");
    }
  }

  async function runReplayBatchGate() {
    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(replayBatchIds);
      } catch {
        setStatus("Batch IDs must be a valid JSON array of strings.");
        return;
      }
      const ids = (Array.isArray(parsed) ? parsed : []).filter(
        (x): x is string => typeof x === "string" && x.trim().length > 0,
      );
      if (!ids.length) {
        setStatus("Batch replay requires a JSON array of execution_ids.");
        return;
      }
      setStatus("Running batch replay gate...");
      const result = await verifyReplayBatch({ execution_ids: ids });
      setReplayResult(result);
      const ok =
        String(result.status ?? "").toUpperCase() === "VERIFIED" &&
        (result.failed ?? 0) === 0;
      setStatus(
        ok
          ? "Batch replay gate VERIFIED."
          : "Batch replay gate FAILED (deployment should be blocked).",
      );
    } catch (err: unknown) {
      console.error(err);
      setReplayResult({ status: "FAILED" });
      setStatus("Batch replay gate FAILED.");
    }
  }

  if (role !== "admin") return null;

  const globalStatus = health?.global_status ?? "UNKNOWN";

  return (
    <div className="panel">
      <h2>Admin Ops Dashboard</h2>

      <div className="button-row">
        <button onClick={() => void loadIntegrationOps()}>Refresh Dashboard</button>
        <button className="btn-secondary" onClick={() => setShowRaw(!showRaw)}>
          {showRaw ? "Hide raw JSON" : "Show raw JSON"}
        </button>
        <button className="btn-secondary" onClick={onClose}>
          Back to Workflow Console
        </button>
      </div>

      {status && <div className="status">{status}</div>}

      {/* ── Integration Health ─────────────────────────────── */}
      {health && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>
            Integration Health —{" "}
            <span
              style={{
                color:
                  globalStatus === "PASS"
                    ? "#16a34a"
                    : globalStatus === "FAIL"
                      ? "#dc2626"
                      : "#d97706",
              }}
            >
              {globalStatus}
            </span>
          </h3>
          {showRaw ? (
            <pre className="console-box">{pretty(health)}</pre>
          ) : (
            <table style={{ fontSize: 12, borderCollapse: "collapse", width: "100%" }}>
              <tbody>
                {(
                  [
                    ["Entra Identity", health.entra_identity?.status],
                    ["LLM Integration", health.llm_integration?.status],
                    ["Approval Ops", health.approval_ops?.status],
                    ["Python Runtime", health.runtime?.python],
                    ["Trust Ledger", health.runtime?.trust_ledger],
                    ["DB Integrity", health.runtime?.db_integrity],
                    ["Replay Verifier", health.runtime?.replay_verifier],
                  ] as [string, string | undefined][]
                ).map(([label, val]) => (
                  <tr key={label}>
                    <td style={{ padding: "3px 8px", color: "#64748b" }}>{label}</td>
                    <td
                      style={{
                        padding: "3px 8px",
                        color:
                          val === "PASS"
                            ? "#16a34a"
                            : val === "FAIL"
                              ? "#dc2626"
                              : "#d97706",
                        fontWeight: 600,
                      }}
                    >
                      {val ?? "UNKNOWN"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Trends ──────────────────────────────────────────── */}
      {trends && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>Trend Summary (24 h)</h3>
          {showRaw ? (
            <pre className="console-box">{pretty(trends)}</pre>
          ) : (
            <div style={{ fontSize: 12, color: "#334155" }}>
              <div>
                Request intercepts: {trends.request_intercepts?.total ?? 0} — allow{" "}
                {trends.request_intercepts?.allow_pct ?? 0}% / restrict{" "}
                {trends.request_intercepts?.restrict_pct ?? 0}%
              </div>
              <div>
                Response governance: {trends.response_governance?.total ?? 0} — allow{" "}
                {trends.response_governance?.allow_pct ?? 0}% / remediate{" "}
                {trends.response_governance?.remediate_pct ?? 0}%
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Effective Config ─────────────────────────────────── */}
      {config && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>Effective Configuration</h3>
          {showRaw ? (
            <pre className="console-box">{pretty(config)}</pre>
          ) : (
            <div style={{ fontSize: 12, color: "#334155" }}>
              <div>Auth mode: <strong>{config.auth?.mode}</strong> — Entra: {config.auth?.entra_enabled ? "enabled" : "disabled"}</div>
              <div>Signing: {config.signing?.enabled ? `enabled (${config.signing.key_mode})` : "disabled"}</div>
              <div>LLM ingestion: {config.llm?.ingestion_enabled ? `enabled — ${config.llm.model}` : "disabled"}</div>
            </div>
          )}
        </div>
      )}

      {/* ── Pending Approvals ────────────────────────────────── */}
      {approvals.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>Pending Approvals ({approvals.length})</h3>
          {approvals.map((a) => (
            <div key={a.approval_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", fontSize: 12 }}>
              <span>{a.approval_id} — risk: {a.risk_level} — {a.requested_by}</span>
              <div className="button-row" style={{ margin: 0 }}>
                <button className="btn-primary" style={{ fontSize: 11, padding: "2px 8px" }} onClick={() => void handleDecideChange(a.approval_id, "approve")}>Approve</button>
                <button className="btn-danger" style={{ fontSize: 11, padding: "2px 8px" }} onClick={() => void handleDecideChange(a.approval_id, "reject")}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Config Change Request ────────────────────────────── */}
      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Submit Config Change Request</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <div>
            <label>Field</label>
            <input value={configField} onChange={(e) => setConfigField(e.target.value)} placeholder="e.g. trust_mode" />
          </div>
          <div>
            <label>Proposed value</label>
            <input value={configValue} onChange={(e) => setConfigValue(e.target.value)} placeholder="e.g. strict" />
          </div>
        </div>
        <label>Reason</label>
        <input value={configReason} onChange={(e) => setConfigReason(e.target.value)} placeholder="Justification for the change" style={{ width: "100%" }} />
        <div className="button-row" style={{ marginTop: 8 }}>
          <button onClick={() => void handleSubmitConfigChange()}>Submit Config Change Request</button>
        </div>
      </div>

      {/* ── Change History ───────────────────────────────────── */}
      {changeHistory.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>Config Change History</h3>
          {showRaw ? (
            <pre className="console-box">{pretty(changeHistory)}</pre>
          ) : (
            <table style={{ fontSize: 11, borderCollapse: "collapse", width: "100%" }}>
              <thead>
                <tr style={{ color: "#64748b" }}>
                  <th style={{ textAlign: "left", padding: "2px 6px" }}>Field</th>
                  <th style={{ textAlign: "left", padding: "2px 6px" }}>Value</th>
                  <th style={{ textAlign: "left", padding: "2px 6px" }}>Status</th>
                  <th style={{ textAlign: "left", padding: "2px 6px" }}>Requested by</th>
                </tr>
              </thead>
              <tbody>
                {changeHistory.slice(0, 10).map((r) => (
                  <tr key={r.request_id}>
                    <td style={{ padding: "2px 6px" }}>{r.field}</td>
                    <td style={{ padding: "2px 6px" }}>{String(r.proposed_value ?? "—")}</td>
                    <td style={{ padding: "2px 6px" }}>{r.status}</td>
                    <td style={{ padding: "2px 6px" }}>{r.requested_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Deterministic Replay Attestation ─────────────────── */}
      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Deterministic Replay Attestation</h3>
        <p className="muted-text">
          Verifies a governed execution can be replayed with identical cryptographic
          bindings. Any hash mismatch blocks promotion.
        </p>

        <label>Execution ID</label>
        <input
          value={replayExecutionId}
          onChange={(e) => setReplayExecutionId(e.target.value)}
          placeholder="execution_id"
          style={{ width: "100%", marginBottom: 8 }}
        />
        <div className="button-row">
          <button onClick={() => void runReplayAttestation()}>Verify Replay</button>
        </div>

        <label style={{ display: "block", marginTop: 16 }}>
          Batch Replay Gate (JSON array of execution IDs)
        </label>
        <textarea
          value={replayBatchIds}
          onChange={(e) => setReplayBatchIds(e.target.value)}
          rows={4}
          style={{ width: "100%", borderRadius: 8, padding: 10, border: "1px solid #cbd5e1" }}
        />
        <div className="button-row" style={{ marginTop: 8 }}>
          <button onClick={() => void runReplayBatchGate()}>Run Batch Replay Gate</button>
        </div>

        {replayResult && !showRaw && (
          <div className="status" style={{ marginTop: 10 }}>
            <strong>Status:</strong>{" "}
            {String(replayResult.status ?? (replayResult.replay_valid ? "VERIFIED" : "UNKNOWN"))}
            {replayResult.total !== undefined && (
              <span>
                {" "}— {replayResult.passed}/{replayResult.total} passed
              </span>
            )}
            {replayResult.certificate_url && (
              <>
                {" "}•{" "}
                <a href={replayResult.certificate_url} target="_blank" rel="noreferrer">
                  Download replay certificate
                </a>
              </>
            )}
          </div>
        )}
        {showRaw && replayResult && (
          <pre className="console-box">{pretty(replayResult as JsonObject)}</pre>
        )}
      </div>
    </div>
  );
}
