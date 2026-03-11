import { useEffect, useState } from "react";
import { exportDecisionPack, listGovernedReports } from "./api";

interface Props {
  executionId: string | null;
}

export default function GovernedReportViewer({ executionId }: Props) {
  const [reports, setReports] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    if (!executionId) return;
    try {
      setStatus("Refreshing report list...");
      const data = await listGovernedReports(executionId);
      setReports(data);
      setStatus("Report list refreshed.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to refresh reports.");
    }
  }

  async function exportLatest() {
    if (!executionId) return;
    try {
      setStatus("Preparing decision pack export...");
      await exportDecisionPack(executionId);
      setStatus("Decision pack exported.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Decision pack export failed.");
    }
  }

  useEffect(() => {
    if (!executionId) return;

    let active = true;
    listGovernedReports(executionId)
      .then((data) => {
        if (active) {
          setReports(data);
          setStatus("Latest reports loaded.");
        }
      })
      .catch((err: unknown) => {
        console.error(err);
        if (active) setStatus("Failed to load latest reports.");
      });

    return () => {
      active = false;
    };
  }, [executionId]);

  if (!executionId) return null;

  return (
    <div className="panel">
      <h3>DIIaC™ Export Dashboard</h3>
      <p className="muted-text">Export and review generated governance artifacts for the latest execution.</p>

      <div className="button-row">
        <button onClick={() => void refresh()}>Refresh</button>
        <button onClick={() => void exportLatest()}>Export Decision Pack</button>
      </div>

      {status && <div className="status">{status}</div>}

      <div className="metrics-grid">
        <div className="metric-card"><h4>Execution ID</h4><p>{executionId}</p></div>
        <div className="metric-card"><h4>Artifacts</h4><p>{reports.length}</p></div>
      </div>

      <ul>
        {reports.map((file) => (
          <li key={file}>
            <a href={`http://localhost:3001/executions/${executionId}/reports/${file}`} target="_blank" rel="noopener noreferrer">
              {file}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
