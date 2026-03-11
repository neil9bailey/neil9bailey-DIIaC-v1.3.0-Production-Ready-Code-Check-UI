import { useState } from "react";
import { runPolicyImpact, type PolicyImpactResponse } from "./api";

interface Props {
  role: string;
}

function severityColor(sev: string): string {
  const s = (sev || "").toLowerCase();
  if (s === "critical" || s === "high") return "var(--red-600)";
  if (s === "medium") return "var(--amber-600)";
  return "var(--green-600)";
}

export default function ImpactViewer({ role }: Props) {
  const [result, setResult] = useState<PolicyImpactResponse | null>(null);
  const [status, setStatus] = useState<string>("");
  const [running, setRunning] = useState(false);

  if (role !== "admin") return null;

  async function analyse() {
    try {
      setRunning(true);
      setStatus("Running policy impact analysis…");
      setResult(null);
      const res = await runPolicyImpact();
      setResult(res);
      setStatus("");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Policy impact analysis failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel">
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ margin: "0 0 3px" }}>Policy Impact Analysis</h2>
        <p className="muted-text" style={{ margin: 0 }}>Evaluate the impact of current policy configuration on controls and compliance posture</p>
      </div>

      <div className="button-row">
        <button className="btn-primary" onClick={() => void analyse()} disabled={running}>
          {running ? "Analysing…" : "Run Policy Impact"}
        </button>
      </div>

      {status && (
        <div className="status" style={{ background: "var(--red-50)", color: "var(--red-700)", borderLeftColor: "var(--red-600)" }}>
          {status}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 14 }}>
          <div className="ledger-grid">
            <div className="ledger-card">
              <div className="ledger-card-label">Severity</div>
              <div className="ledger-card-value" style={{ color: severityColor(result.severity), fontSize: 15, fontWeight: 800, fontFamily: "var(--font-sans)" }}>
                {result.severity?.toUpperCase() ?? "—"}
              </div>
            </div>
            <div className="ledger-card">
              <div className="ledger-card-label">Impacted Controls</div>
              <div className="ledger-card-value" style={{ fontSize: 18, fontWeight: 800, fontFamily: "var(--font-sans)" }}>{result.impacted_controls ?? "—"}</div>
            </div>
            <div className="ledger-card">
              <div className="ledger-card-label">Evaluated At</div>
              <div className="ledger-card-value" style={{ fontFamily: "var(--font-sans)", fontSize: 11 }}>{result.evaluated_at ?? "—"}</div>
            </div>
            {result.findings && (
              <div className="ledger-card" style={{ gridColumn: "1 / -1" }}>
                <div className="ledger-card-label">Findings</div>
                <div className="ledger-card-value" style={{ fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 400, color: "var(--slate-600)" }}>{result.findings}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
