import { useEffect, useState } from "react";
import { exportDecisionPack, listGovernedReports, downloadGovernedReport } from "./api";

interface Props {
  executionId: string | null;
}

function fileIcon(filename: string): string {
  if (filename.endsWith(".md")) return "📄";
  if (filename.endsWith(".json")) return "🗂";
  if (filename.endsWith(".pdf")) return "📕";
  if (filename.endsWith(".docx")) return "📘";
  if (filename.endsWith(".zip")) return "📦";
  return "📋";
}

export default function GovernedReportViewer({ executionId }: Props) {
  const [reports, setReports] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    if (!executionId) return;
    try {
      setStatus("Refreshing artifact list…");
      const data = await listGovernedReports(executionId);
      setReports(data);
      setStatus("Artifact list refreshed.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to refresh reports.");
    }
  }

  async function exportLatest() {
    if (!executionId) return;
    try {
      setStatus("Preparing decision pack export…");
      await exportDecisionPack(executionId);
      setStatus("✔ Decision pack exported successfully.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Decision pack export failed.");
    }
  }

  useEffect(() => {
    if (!executionId) return;
    let active = true;
    listGovernedReports(executionId)
      .then((data) => { if (active) { setReports(data); setStatus(""); } })
      .catch((err: unknown) => { console.error(err); if (active) setStatus("Failed to load reports."); });
    return () => { active = false; };
  }, [executionId]);

  if (!executionId) return null;

  return (
    <div className="panel">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: "0 0 3px" }}>Step 3 — Export Artifacts</h2>
          <p className="muted-text" style={{ margin: 0 }}>
            Download governed decision artifacts, reports, and evidence chain for execution{" "}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{executionId}</span>
          </p>
        </div>
        <span style={{ background: "var(--green-50)", color: "var(--green-700)", border: "1px solid var(--green-100)", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, flexShrink: 0, marginLeft: 16 }}>
          {reports.length} Artifact{reports.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Execution summary */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, marginBottom: 14 }}>
        <div className="ledger-card">
          <div className="ledger-card-label">Execution ID</div>
          <div className="ledger-card-value">{executionId}</div>
        </div>
        <div className="ledger-card" style={{ textAlign: "center", minWidth: 100 }}>
          <div className="ledger-card-label">Artifacts</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: "var(--navy-900)" }}>{reports.length}</div>
        </div>
      </div>

      <div className="button-row" style={{ marginBottom: 14 }}>
        <button className="btn-primary" onClick={() => void exportLatest()}>
          ⬇ Export Decision Pack
        </button>
        <button className="btn-secondary" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      {status && (
        <div
          className="status"
          style={status.startsWith("✔") ? { background: "var(--green-50)", color: "var(--green-700)", borderLeftColor: "var(--green-600)" } : {}}
        >
          {status}
        </div>
      )}

      {reports.length > 0 ? (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--slate-400)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            Artifact Files
          </div>
          <div className="report-file-list">
            {reports.map((file) => (
              <div key={file} className="report-file-item">
                <span className="report-file-icon">{fileIcon(file)}</span>
                <span className="report-file-name">{file}</span>
                <button
                  className="btn-secondary report-file-btn"
                  onClick={() => void downloadGovernedReport(executionId!, file)}
                >
                  Download
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "20px", color: "var(--slate-400)", fontSize: 12 }}>
          No artifacts found. Run a governance execution first.
        </div>
      )}
    </div>
  );
}
