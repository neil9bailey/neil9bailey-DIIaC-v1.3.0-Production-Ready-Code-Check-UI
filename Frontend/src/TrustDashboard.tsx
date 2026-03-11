import { useEffect, useState } from "react";
import { fetchTrustDashboard, type TrustDashboardResponse } from "./api";

interface Props {
  role: string;
}

export default function TrustDashboard({ role }: Props) {
  const [data, setData] = useState<TrustDashboardResponse | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (role !== "admin") return;
    async function load() {
      try {
        setLoading(true);
        setStatus("Loading trust state…");
        setData(null);
        const res = await fetchTrustDashboard();
        setData(res);
        setStatus("");
      } catch (err: unknown) {
        console.error(err);
        setStatus("Failed to load trust state.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [role]);

  if (role !== "admin") return null;

  return (
    <div className="panel">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: "0 0 3px" }}>Trust Ledger</h2>
          <p className="muted-text" style={{ margin: 0 }}>Immutable audit ledger validity and integrity status</p>
        </div>
        {data && (
          <span className={`status-badge ${data.valid ? "pass" : "fail"}`} style={{ fontSize: 12, padding: "4px 12px" }}>
            {data.valid ? "VALID" : "INVALID"}
          </span>
        )}
      </div>

      {loading && <div className="status">Loading trust state…</div>}
      {status && !loading && <div className="status" style={{ background: "var(--red-50)", color: "var(--red-700)", borderLeftColor: "var(--red-600)" }}>{status}</div>}

      {data && (
        <div className="ledger-grid">
          <div className="ledger-card">
            <div className="ledger-card-label">Validity</div>
            <div className="ledger-card-value" style={{ color: data.valid ? "var(--green-600)" : "var(--red-600)", fontSize: 16, fontWeight: 800, fontFamily: "var(--font-sans)" }}>
              {data.valid ? "✔ Valid" : "✘ Invalid"}
            </div>
          </div>
          <div className="ledger-card">
            <div className="ledger-card-label">Record Count</div>
            <div className="ledger-card-value" style={{ fontSize: 20, fontWeight: 800, fontFamily: "var(--font-sans)" }}>{data.records}</div>
          </div>
          <div className="ledger-card">
            <div className="ledger-card-label">Frozen</div>
            <div className="ledger-card-value" style={{ color: data.frozen ? "var(--amber-600)" : "var(--green-600)", fontSize: 14, fontFamily: "var(--font-sans)" }}>
              {data.frozen ? "⚠ Frozen" : "Active"}
            </div>
          </div>
          <div className="ledger-card" style={{ gridColumn: "1 / -1" }}>
            <div className="ledger-card-label">Ledger Root Hash</div>
            <div className="ledger-card-value">{data.ledger_root ?? "—"}</div>
          </div>
        </div>
      )}
    </div>
  );
}
