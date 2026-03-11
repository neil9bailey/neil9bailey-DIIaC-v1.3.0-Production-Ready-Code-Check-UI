import { useMemo, useState } from "react";
import {
  downloadAuditExport,
  fetchAdminDbStatus,
  fetchAdminHealth,
  fetchAdminLogs,
  fetchAdminMetrics,
  fetchBridgeLedgerLogs,
  fetchBridgeTrustStatus,
  fetchContainerStatus,
  fetchExecutionLogs,
  fetchServiceStatus,
  generateAuditExport,
  listAuditExports,
  runDbCompact,
  verifyExecution,
  type AdminDbStatusResponse,
  type AdminHealthResponse,
  type AdminMetricsResponse,
  type BridgeLedgerLogsResponse,
  type BridgeTrustStatusResponse,
  type ContainerStatusResponse,
  type JsonObject,
  type ServiceStatusResponse,
  type VerifyExecutionResponse,
  type AuditExportListItem,
} from "./api";

interface Props {
  role: string;
  executionId: string | null;
}

type AdminTab = "overview" | "exports" | "logs" | "db";

function pretty(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

function countRows(data: JsonObject | JsonObject[] | null): number {
  if (!data) return 0;
  if (Array.isArray(data)) return data.length;
  if (Array.isArray(data.logs)) return data.logs.length;
  return 1;
}

export default function AdminConsolePanel({ role, executionId }: Props) {
  const [tab, setTab] = useState<AdminTab>("overview");
  const [showRaw, setShowRaw] = useState(false);
  const [targetExecutionId, setTargetExecutionId] = useState(executionId || "");
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatusResponse | null>(null);
  const [containerStatus, setContainerStatus] = useState<ContainerStatusResponse | null>(null);
  const [verification, setVerification] = useState<VerifyExecutionResponse | null>(null);
  const [backendLogs, setBackendLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [ledgerLogs, setLedgerLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [bridgeLedgerLogs, setBridgeLedgerLogs] = useState<BridgeLedgerLogsResponse | null>(null);
  const [bridgeTrustStatus, setBridgeTrustStatus] = useState<BridgeTrustStatusResponse | null>(null);
  const [executionLogs, setExecutionLogs] = useState<JsonObject | null>(null);
  const [dbStatus, setDbStatus] = useState<AdminDbStatusResponse | null>(null);
  const [dbMaintenance, setDbMaintenance] = useState<JsonObject | null>(null);
  const [auditPayload, setAuditPayload] = useState<JsonObject | null>(null);
  const [auditStoragePath, setAuditStoragePath] = useState("");
  const [auditStoragePathRelative, setAuditStoragePathRelative] = useState("");
  const [auditExports, setAuditExports] = useState<AuditExportListItem[]>([]);
  const [status, setStatus] = useState("");

  const effectiveExecutionId = useMemo(() => targetExecutionId.trim() || executionId || "", [targetExecutionId, executionId]);

  if (role !== "admin") return null;

  async function loadOverview() {
    try {
      setStatus("Refreshing service status, metrics, containers, and DB integrity...");
      const [h, m, s, c, db] = await Promise.all([
        fetchAdminHealth(),
        fetchAdminMetrics(),
        fetchServiceStatus(),
        fetchContainerStatus(),
        fetchAdminDbStatus(),
      ]);
      setHealth(h);
      setMetrics(m);
      setServiceStatus(s);
      setContainerStatus(c);
      setDbStatus(db);
      setStatus("Overview refreshed.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to refresh overview.");
    }
  }

  async function loadLogs(source: "backend" | "ledger") {
    try {
      setStatus(`Loading ${source} logs...`);
      const logs = await fetchAdminLogs(source);
      if (source === "backend") setBackendLogs(logs);
      if (source === "ledger") setLedgerLogs(logs);
      setStatus(`${source} logs loaded.`);
    } catch (err: unknown) {
      console.error(err);
      setStatus(`Failed to load ${source} logs.`);
    }
  }

  async function loadBridgeLedger() {
    try {
      setStatus("Loading bridge ledger logs...");
      const [logs, trust] = await Promise.all([fetchBridgeLedgerLogs(), fetchBridgeTrustStatus()]);
      setBridgeLedgerLogs(logs);
      setBridgeTrustStatus(trust);
      setStatus(`Bridge ledger loaded: ${logs.total} record(s), root ${logs.ledger_root.slice(0, 16)}…`);
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to load bridge ledger.");
    }
  }

  async function loadExecutionLogsAndVerify() {
    if (!effectiveExecutionId) {
      setStatus("Execution ID is required.");
      return;
    }

    try {
      setStatus("Loading execution logs + verification...");
      const [logs, verify] = await Promise.all([
        fetchExecutionLogs(effectiveExecutionId),
        verifyExecution(effectiveExecutionId),
      ]);
      setExecutionLogs(logs);
      setVerification(verify);
      setStatus("Execution logs + verification loaded.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to load execution logs/verification.");
    }
  }

  async function generateAudit() {
    if (!effectiveExecutionId) {
      setStatus("Execution ID is required.");
      return;
    }

    try {
      setStatus("Generating audit export...");
      const audit = await generateAuditExport([effectiveExecutionId]);
      const download = await downloadAuditExport(audit.audit_export_id);
      setAuditPayload({
        audit_export_id: audit.audit_export_id,
        download_url: audit.download_url,
        storage_path: audit.storage_path || "",
        storage_path_relative: audit.storage_path_relative || "",
        bundle: download,
      });
      setAuditStoragePath(audit.storage_path || "");
      setAuditStoragePathRelative(audit.storage_path_relative || "");
      setStatus(
        audit.storage_path
          ? `Audit export generated + downloaded. Server artifact: ${audit.storage_path}`
          : "Audit export generated + downloaded. Browser save location is controlled by browser settings.",
      );
      const listing = await listAuditExports();
      setAuditExports(listing.exports || []);
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to generate audit export.");
    }
  }

  async function refreshAuditExports() {
    try {
      setStatus("Loading audit export history...");
      const listing = await listAuditExports();
      setAuditExports(listing.exports || []);
      setStatus(`Loaded ${listing.count || 0} audit export record(s).`);
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to load audit export history.");
    }
  }

  async function compactDb() {
    try {
      setStatus("Running DB maintenance (VACUUM)...");
      const op = await runDbCompact();
      setDbMaintenance(op);
      setDbStatus(await fetchAdminDbStatus());
      setStatus("DB maintenance completed.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("DB maintenance failed.");
    }
  }

  return (
    <div className="panel">
      <h2>DIIaC™ Operations Dashboard</h2>
      <p className="muted-text">
        Service health, export operations, logs, and database maintenance in one structured admin dashboard.
      </p>

      <div className="tab-row">
        <button className={tab === "overview" ? "tab-active" : ""} onClick={() => setTab("overview")}>Overview</button>
        <button className={tab === "exports" ? "tab-active" : ""} onClick={() => setTab("exports")}>Exports & Verification</button>
        <button className={tab === "logs" ? "tab-active" : ""} onClick={() => setTab("logs")}>Logs</button>
        <button className={tab === "db" ? "tab-active" : ""} onClick={() => setTab("db")}>DB Maintenance</button>
        <button className="btn-ghost" style={{ marginLeft: "auto" }} onClick={() => setShowRaw(!showRaw)}>{showRaw ? "Hide JSON" : "Show JSON"}</button>
      </div>

      <div className="id-row">
        <label>Execution ID:</label>
        <input value={targetExecutionId} onChange={(e) => setTargetExecutionId(e.target.value)} placeholder="execution-id" />
      </div>

      {status && <div className="status">{status}</div>}

      {tab === "overview" && (
        <>
          <div className="button-row">
            <button onClick={() => void loadOverview()}>Refresh Overview</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Service Status</h4><p>{serviceStatus?.overall_ok ? "Operational" : "Check required"}</p></div>
            <div className="metric-card"><h4>Runtime Health</h4><p>{health?.status || "Unknown"}</p></div>
            <div className="metric-card"><h4>Ledger Records</h4><p>{metrics?.ledger_record_count ?? health?.ledger_record_count ?? 0}</p></div>
            <div className="metric-card"><h4>Container Visibility</h4><p>{containerStatus?.available ? "Available" : "Unavailable"}</p></div>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Executions Total</h4><p>{metrics?.executions_total ?? 0}</p></div>
            <div className="metric-card"><h4>Signed Recent</h4><p>{metrics?.signed_recent_executions ?? 0}</p></div>
            <div className="metric-card"><h4>DB Path</h4><p>{dbStatus?.db_path || "n/a"}</p></div>
            <div className="metric-card"><h4>Key Registry Integrity</h4><p>{String(dbStatus?.integrity?.key_registry_ok ?? false)}</p></div>
          </div>
        </>
      )}

      {tab === "exports" && (
        <>
          <div className="button-row">
            <button onClick={() => void loadExecutionLogsAndVerify()}>Validate Execution</button>
            <button onClick={() => void generateAudit()}>Generate Audit Export</button>
            <button onClick={() => void refreshAuditExports()}>Refresh Audit Export History</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Execution</h4><p>{effectiveExecutionId || "Not set"}</p></div>
            <div className="metric-card"><h4>Verification</h4><p>{verification?.status || "Not run"}</p></div>
            <div className="metric-card"><h4>Signature Present</h4><p>{String(verification?.signature_present ?? false)}</p></div>
            <div className="metric-card"><h4>Audit Export</h4><p>{String(auditPayload?.audit_export_id || "Not generated")}</p></div>
            <div className="metric-card"><h4>Audit Runtime Path</h4><p>{auditStoragePath || "Not available"}</p></div>
            <div className="metric-card"><h4>Audit Workspace Path</h4><p>{auditStoragePathRelative || "Not available"}</p></div>
          </div>
          <p className="muted-text">Download destination on your machine is controlled by your browser/OS settings.</p>
          {auditExports.length > 0 && (
            <div className="console-box" style={{ marginTop: 12 }}>
              <h4>Audit Export History</h4>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>Export ID</th>
                    <th style={{ textAlign: "left" }}>Created</th>
                    <th style={{ textAlign: "left" }}>Executions</th>
                      <th style={{ textAlign: "left" }}>Runtime Path</th>
                      <th style={{ textAlign: "left" }}>Workspace Path</th>
                      <th style={{ textAlign: "left" }}>Size</th>
                  </tr>
                </thead>
                <tbody>
                  {auditExports.map((item) => (
                    <tr key={item.audit_export_id}>
                      <td>{item.audit_export_id}</td>
                      <td>{item.created_at || "n/a"}</td>
                      <td>{(item.execution_ids || []).join(", ") || "n/a"}</td>
                      <td>{item.storage_path || "n/a"}</td>
                      <td>{item.storage_path_relative || "n/a"}</td>
                      <td>{typeof item.size_bytes === "number" ? `${item.size_bytes} bytes` : "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === "logs" && (
        <>
          <div className="button-row">
            <button onClick={() => void loadLogs("backend")}>Load Backend Logs</button>
            <button onClick={() => void loadLogs("ledger")}>Load Ledger Logs</button>
            <button onClick={() => void loadBridgeLedger()}>Load Bridge Ledger</button>
            <button onClick={() => void loadExecutionLogsAndVerify()}>Load Execution Logs</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Backend Logs</h4><p>{countRows(backendLogs)}</p></div>
            <div className="metric-card"><h4>Ledger Logs</h4><p>{countRows(ledgerLogs)}</p></div>
            <div className="metric-card"><h4>Bridge Ledger Records</h4><p>{bridgeLedgerLogs?.total ?? bridgeTrustStatus?.ledger_records ?? "—"}</p></div>
            <div className="metric-card"><h4>Bridge Ledger Root</h4><p style={{ fontFamily: "monospace", fontSize: 11 }}>{bridgeLedgerLogs?.ledger_root?.slice(0, 16) ?? bridgeTrustStatus?.ledger_root?.slice(0, 16) ?? "GENESIS"}</p></div>
            <div className="metric-card"><h4>Execution Logs</h4><p>{countRows(executionLogs)}</p></div>
            <div className="metric-card"><h4>Routes Instrumented</h4><p>{metrics?.routes ? Object.keys(metrics.routes).length : 0}</p></div>
          </div>
        </>
      )}

      {tab === "db" && (
        <>
          <div className="button-row">
            <button onClick={() => void fetchAdminDbStatus().then(setDbStatus)}>Refresh DB Status</button>
            <button onClick={() => void compactDb()}>Run DB Compact</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Role Inputs</h4><p>{dbStatus?.tables?.role_inputs ?? 0}</p></div>
            <div className="metric-card"><h4>Executions</h4><p>{dbStatus?.tables?.executions ?? 0}</p></div>
            <div className="metric-card"><h4>Backend Logs</h4><p>{dbStatus?.tables?.backend_logs ?? 0}</p></div>
            <div className="metric-card"><h4>Ledger Logs</h4><p>{dbStatus?.tables?.ledger_logs ?? 0}</p></div>
          </div>
        </>
      )}

      {showRaw && (
        <>
          {health && <pre className="console-box">{pretty(health)}</pre>}
          {metrics && <pre className="console-box">{pretty(metrics)}</pre>}
          {serviceStatus && <pre className="console-box">{pretty(serviceStatus)}</pre>}
          {containerStatus && <pre className="console-box">{pretty(containerStatus)}</pre>}
          {verification && <pre className="console-box">{pretty(verification)}</pre>}
          {executionLogs && <pre className="console-box">{pretty(executionLogs)}</pre>}
          {auditPayload && <pre className="console-box">{pretty(auditPayload)}</pre>}
          {backendLogs && <pre className="console-box">{pretty(backendLogs)}</pre>}
          {ledgerLogs && <pre className="console-box">{pretty(ledgerLogs)}</pre>}
          {bridgeLedgerLogs && <pre className="console-box">{pretty(bridgeLedgerLogs)}</pre>}
          {bridgeTrustStatus && <pre className="console-box">{pretty(bridgeTrustStatus)}</pre>}
          {dbStatus && <pre className="console-box">{pretty(dbStatus)}</pre>}
          {dbMaintenance && <pre className="console-box">{pretty(dbMaintenance)}</pre>}
        </>
      )}
    </div>
  );
}
