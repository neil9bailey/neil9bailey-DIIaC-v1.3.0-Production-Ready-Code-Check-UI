import { useCallback, useEffect, useMemo, useState } from "react";
import {
  downloadAuditExport,
  downloadAuditExportFile,
  fetchAdminDbStatus,
  fetchAdminHealth,
  fetchAdminLogs,
  fetchAdminMetrics,
  fetchExecutionLogs,
  fetchServiceStatus,
  generateAuditExport,
  listAuditExports,
  runDbCompact,
  verifyExecution,
  type AdminDbStatusResponse,
  type AdminHealthResponse,
  type AdminMetricsResponse,
  type AuditExportListItem,
  type JsonObject,
  type ServiceStatusResponse,
  type VerifyExecutionResponse,
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

function freshnessLabel(lastRefreshAt: number | null, _tick: number): string {
  if (!lastRefreshAt) return "Never";
  const ageSec = Math.floor((Date.now() - lastRefreshAt) / 1000);
  if (ageSec < 10) return "Live";
  if (ageSec < 90) return `${ageSec}s old`;
  return `Stale (${ageSec}s old)`;
}

export default function AdminConsolePanel({ role, executionId }: Props) {
  const [tab, setTab] = useState<AdminTab>("overview");
  const [showRaw, setShowRaw] = useState(false);
  const [targetExecutionId, setTargetExecutionId] = useState(executionId || "");
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatusResponse | null>(null);
  const [verification, setVerification] = useState<VerifyExecutionResponse | null>(null);
  const [backendLogs, setBackendLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [ledgerLogs, setLedgerLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [executionLogs, setExecutionLogs] = useState<JsonObject | null>(null);
  const [dbStatus, setDbStatus] = useState<AdminDbStatusResponse | null>(null);
  const [dbMaintenance, setDbMaintenance] = useState<JsonObject | null>(null);
  const [auditPayload, setAuditPayload] = useState<JsonObject | null>(null);
  const [auditStoragePath, setAuditStoragePath] = useState("");
  const [auditStoragePathRelative, setAuditStoragePathRelative] = useState("");
  const [auditExports, setAuditExports] = useState<AuditExportListItem[]>([]);
  const [status, setStatus] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshAt, setLastRefreshAt] = useState<number | null>(null);
  const [freshnessTick, setFreshnessTick] = useState(0);

  const effectiveExecutionId = useMemo(
    () => targetExecutionId.trim() || executionId || "",
    [targetExecutionId, executionId],
  );

  const markRefreshed = useCallback(() => {
    setLastRefreshAt(Date.now());
  }, []);

  const loadOverview = useCallback(async (silent = false) => {
    try {
      if (!silent) setStatus("Refreshing service status, metrics, and DB integrity...");
      const [h, m, s, db] = await Promise.all([
        fetchAdminHealth(),
        fetchAdminMetrics(),
        fetchServiceStatus(),
        fetchAdminDbStatus(),
      ]);
      setHealth(h);
      setMetrics(m);
      setServiceStatus(s);
      setDbStatus(db);
      markRefreshed();
      if (!silent) setStatus("Overview refreshed.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(err);
      if (!silent) {
        if (msg.includes("no_diiac_role") || msg.includes("authentication_required")) {
          setStatus("Access denied: your account does not have the required DIIaC admin role. Contact your admin to configure role or group mappings.");
        } else if (msg.includes("401")) {
          setStatus("Authentication required. Ensure you are signed in with a valid Entra ID token.");
        } else {
          setStatus("Failed to refresh overview. Ensure the bridge is running and accessible.");
        }
      }
    }
  }, [markRefreshed]);

  const loadLogs = useCallback(async (source: "backend" | "ledger", silent = false) => {
    try {
      if (!silent) setStatus(`Loading ${source} logs...`);
      const logs = await fetchAdminLogs(source);
      if (source === "backend") setBackendLogs(logs);
      if (source === "ledger") setLedgerLogs(logs);
      markRefreshed();
      if (!silent) setStatus(`${source} logs loaded.`);
    } catch (err: unknown) {
      console.error(err);
      if (!silent) setStatus(`Failed to load ${source} logs.`);
    }
  }, [markRefreshed]);

  const loadExecutionLogsAndVerify = useCallback(async (silent = false) => {
    if (!effectiveExecutionId) {
      if (!silent) setStatus("Execution ID is required.");
      return;
    }

    try {
      if (!silent) setStatus("Loading execution logs + verification...");
      const [logs, verify] = await Promise.all([
        fetchExecutionLogs(effectiveExecutionId),
        verifyExecution(effectiveExecutionId),
      ]);
      setExecutionLogs(logs);
      setVerification(verify);
      markRefreshed();
      if (!silent) setStatus("Execution logs + verification loaded.");
    } catch (err: unknown) {
      console.error(err);
      if (!silent) setStatus("Failed to load execution logs/verification.");
    }
  }, [effectiveExecutionId, markRefreshed]);

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
      await downloadAuditExportFile(audit.audit_export_id);
      setStatus(`Audit export generated and saved to your downloads: ${audit.audit_export_id}.json`);
      const listing = await listAuditExports();
      setAuditExports(listing.exports || []);
      markRefreshed();
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to generate audit export.");
    }
  }

  const refreshAuditExports = useCallback(async (silent = false) => {
    try {
      if (!silent) setStatus("Loading audit export history...");
      const listing = await listAuditExports();
      setAuditExports(listing.exports || []);
      markRefreshed();
      if (!silent) setStatus(`Loaded ${listing.count || 0} audit export record(s).`);
    } catch (err: unknown) {
      console.error(err);
      if (!silent) setStatus("Failed to load audit export history.");
    }
  }, [markRefreshed]);

  async function compactDb() {
    try {
      setStatus("Running DB maintenance (VACUUM)...");
      const op = await runDbCompact();
      setDbMaintenance(op);
      setDbStatus(await fetchAdminDbStatus());
      markRefreshed();
      setStatus("DB maintenance completed.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("DB maintenance failed.");
    }
  }

  useEffect(() => {
    if (role !== "admin") return;
    if (tab === "overview") {
      void loadOverview(true);
    } else if (tab === "exports") {
      void refreshAuditExports(true);
    } else if (tab === "logs") {
      void loadLogs("backend", true);
      void loadLogs("ledger", true);
    }
  }, [role, tab, loadOverview, refreshAuditExports, loadLogs]);

  useEffect(() => {
    if (role !== "admin" || !autoRefresh) return;
    if (tab === "db") return;

    const intervalMs = tab === "overview" ? 30000 : (tab === "logs" ? 45000 : 60000);
    const interval = setInterval(() => {
      if (tab === "overview") {
        void loadOverview(true);
      } else if (tab === "logs") {
        void loadLogs("backend", true);
        void loadLogs("ledger", true);
      } else if (tab === "exports") {
        void refreshAuditExports(true);
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [role, autoRefresh, tab, loadOverview, loadLogs, refreshAuditExports]);

  useEffect(() => {
    if (!lastRefreshAt) return;
    const interval = setInterval(() => setFreshnessTick((t) => t + 1), 5000);
    return () => clearInterval(interval);
  }, [lastRefreshAt]);

  if (role !== "admin") return null;

  return (
    <div className="panel">
      <h2>DIIaC Operations Dashboard</h2>
      <p className="muted-text">
        Service health, export operations, logs, and database maintenance in one structured admin dashboard.
      </p>

      <div className="tab-row">
        <button className={tab === "overview" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("overview")}>Overview</button>
        <button className={tab === "exports" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("exports")}>Exports</button>
        <button className={tab === "logs" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("logs")}>Logs</button>
        <button className={tab === "db" ? "btn-primary" : "btn-secondary"} onClick={() => setTab("db")}>DB Maintenance</button>
        <button className="btn-secondary" onClick={() => setAutoRefresh((v) => !v)}>Auto Refresh: {autoRefresh ? "ON" : "OFF"}</button>
        <button className="btn-secondary" onClick={() => setShowRaw(!showRaw)}>{showRaw ? "Hide raw JSON" : "Show raw JSON"}</button>
      </div>

      <div className="id-row" style={{ alignItems: "center", gap: 12 }}>
        <label>Execution ID:</label>
        <input value={targetExecutionId} onChange={(e) => setTargetExecutionId(e.target.value)} placeholder="execution-id" />
        <span className="muted-text" style={{ fontSize: 12 }}>
          Freshness: {freshnessLabel(lastRefreshAt, freshnessTick)}
        </span>
      </div>

      {status && <div className="status">{status}</div>}

      {tab === "overview" && (
        <>
          <div className="button-row">
            <button onClick={() => void loadOverview(false)}>Refresh Overview</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Service Status</h4><p>{serviceStatus?.overall_ok ? "Operational" : "Check required"}</p></div>
            <div className="metric-card"><h4>Runtime Health</h4><p>{health?.status || "Unknown"}</p></div>
            <div className="metric-card"><h4>Ledger Records</h4><p>{metrics?.ledger_record_count ?? health?.ledger_record_count ?? 0}</p></div>
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
            <button onClick={() => void loadExecutionLogsAndVerify(false)}>Validate Execution</button>
            <button onClick={() => void generateAudit()}>Generate Audit Export</button>
            <button onClick={() => void refreshAuditExports(false)}>Refresh Audit Export History</button>
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
                    <th style={{ textAlign: "left" }}>Download</th>
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
                      <td>
                        <button
                          style={{ padding: "2px 10px", cursor: "pointer" }}
                          onClick={() => {
                            setStatus(`Downloading ${item.audit_export_id}...`);
                            downloadAuditExportFile(item.audit_export_id)
                              .then(() => setStatus(`Downloaded ${item.audit_export_id}.`))
                              .catch(() => setStatus(`Failed to download ${item.audit_export_id}.`));
                          }}
                        >
                          Download
                        </button>
                      </td>
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
            <button onClick={() => void loadLogs("backend", false)}>Load Backend Logs</button>
            <button onClick={() => void loadLogs("ledger", false)}>Load Ledger Logs</button>
            <button onClick={() => void loadExecutionLogsAndVerify(false)}>Load Execution Logs</button>
          </div>
          <div className="metrics-grid">
            <div className="metric-card"><h4>Backend Logs</h4><p>{countRows(backendLogs)}</p></div>
            <div className="metric-card"><h4>Ledger Logs</h4><p>{countRows(ledgerLogs)}</p></div>
            <div className="metric-card"><h4>Execution Logs</h4><p>{countRows(executionLogs)}</p></div>
            <div className="metric-card"><h4>Routes Instrumented</h4><p>{metrics?.routes ? Object.keys(metrics.routes).length : 0}</p></div>
          </div>
        </>
      )}

      {tab === "db" && (
        <>
          <div className="button-row">
            <button onClick={() => void fetchAdminDbStatus().then((v) => { setDbStatus(v); markRefreshed(); })}>Refresh DB Status</button>
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
          {verification && <pre className="console-box">{pretty(verification)}</pre>}
          {executionLogs && <pre className="console-box">{pretty(executionLogs)}</pre>}
          {auditPayload && <pre className="console-box">{pretty(auditPayload)}</pre>}
          {backendLogs && <pre className="console-box">{pretty(backendLogs)}</pre>}
          {ledgerLogs && <pre className="console-box">{pretty(ledgerLogs)}</pre>}
          {dbStatus && <pre className="console-box">{pretty(dbStatus)}</pre>}
          {dbMaintenance && <pre className="console-box">{pretty(dbMaintenance)}</pre>}
        </>
      )}
    </div>
  );
}
