import { useState } from "react";
import {
  downloadAuditExport,
  fetchAdminHealth,
  fetchAdminLogs,
  fetchExecutionLogs,
  generateAuditExport,
  verifyExecution,
  type AdminHealthResponse,
  type JsonObject,
  type VerifyExecutionResponse,
} from "./api";

interface Props {
  role: string;
  executionId: string | null;
}

function pretty(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

export default function AdminConsolePanel({ role, executionId }: Props) {
  const [targetExecutionId, setTargetExecutionId] = useState(executionId || "");
  const [metrics, setMetrics] = useState<AdminHealthResponse | null>(null);
  const [verification, setVerification] = useState<VerifyExecutionResponse | null>(null);
  const [backendLogs, setBackendLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [ledgerLogs, setLedgerLogs] = useState<JsonObject | JsonObject[] | null>(null);
  const [executionLogs, setExecutionLogs] = useState<JsonObject | null>(null);
  const [auditPayload, setAuditPayload] = useState<JsonObject | null>(null);
  const [status, setStatus] = useState("");

  if (role !== "admin") return null;

  async function loadMetrics() {
    try {
      setStatus("Loading metrics...");
      setMetrics(await fetchAdminHealth());
      setStatus("Metrics loaded.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to load metrics.");
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

  async function loadExecutionLogsAndVerify() {
    const effectiveExecutionId = targetExecutionId.trim() || executionId || "";
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
    const effectiveExecutionId = targetExecutionId.trim() || executionId || "";
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
        bundle: download,
      });
      setStatus("Audit export generated + downloaded.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to generate audit export.");
    }
  }

  return (
    <div className="panel">
      <h2>Admin Console — Logs &amp; Metrics</h2>

      <div className="button-row">
        <button onClick={() => void loadMetrics()}>Load Metrics</button>
        <button onClick={() => void loadLogs("backend")}>Backend Logs</button>
        <button onClick={() => void loadLogs("ledger")}>Ledger Logs</button>
      </div>

      <div>
        <label>Execution ID:</label>
        <input
          value={targetExecutionId}
          onChange={(e) => setTargetExecutionId(e.target.value)}
          placeholder="execution-id"
        />
        <button onClick={() => void loadExecutionLogsAndVerify()}>Load Execution Logs/Verify</button>
        <button onClick={() => void generateAudit()}>Generate Audit Export</button>
      </div>

      {status && <div className="status">{status}</div>}

      {metrics && <pre className="console-box">{pretty(metrics)}</pre>}
      {verification && <pre className="console-box">{pretty(verification)}</pre>}
      {executionLogs && <pre className="console-box">{pretty(executionLogs)}</pre>}
      {auditPayload && <pre className="console-box">{pretty(auditPayload)}</pre>}
      {backendLogs && <pre className="console-box">{pretty(backendLogs)}</pre>}
      {ledgerLogs && <pre className="console-box">{pretty(ledgerLogs)}</pre>}
    </div>
  );
}
