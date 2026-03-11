import { useEffect, useState } from "react";
import { exportDecisionPack, listGovernedReports } from "./api";

interface Props {
  executionId: string | null;
}

export default function GovernedReportViewer({ executionId }: Props) {
  const [reports, setReports] = useState<string[]>([]);

  async function refresh() {
    if (!executionId) return;
    try {
      const data = await listGovernedReports(executionId);
      setReports(data);
    } catch (err: unknown) {
      console.error(err);
    }
  }

  async function exportLatest() {
    if (!executionId) return;
    await exportDecisionPack(executionId);
  }

  useEffect(() => {
    if (!executionId) return;

    let active = true;
    listGovernedReports(executionId)
      .then((data) => {
        if (active) setReports(data);
      })
      .catch((err: unknown) => {
        console.error(err);
      });

    return () => {
      active = false;
    };
  }, [executionId]);

  if (!executionId) return null;

  return (
    <div className="panel">
      <h3>Governed Reports</h3>

      <button onClick={() => void refresh()}>Refresh</button>

      <button onClick={() => void exportLatest()}>Export Latest Decision Pack</button>

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
