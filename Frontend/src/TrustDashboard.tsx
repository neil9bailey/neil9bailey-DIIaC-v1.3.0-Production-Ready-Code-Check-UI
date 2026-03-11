import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchTrustDashboard, type TrustDashboardResponse } from "./api";

interface Props {
  role: string;
}

export default function TrustDashboard({ role }: Props) {
  const [data, setData] = useState<TrustDashboardResponse | null>(null);
  const [status, setStatus] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [loading, setLoading] = useState(false);

  const pollMs = 30000;
  const staleMs = 90000;

  const freshness = useMemo(() => {
    if (!lastUpdatedAt) return "Never";
    const ageMs = Date.now() - lastUpdatedAt;
    if (ageMs < 10000) return "Live";
    if (ageMs < staleMs) return `${Math.floor(ageMs / 1000)}s old`;
    return `Stale (${Math.floor(ageMs / 1000)}s old)`;
  }, [lastUpdatedAt, refreshTick]);

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setLoading(true);
        setStatus("Loading trust state...");
      }
      const res = await fetchTrustDashboard();
      setData(res);
      setLastUpdatedAt(Date.now());
      if (!silent) {
        setStatus("Trust state loaded.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(err);
      if (msg.includes("no_diiac_role") || msg.includes("403")) {
        setStatus("Access denied: DIIaC role not resolved. Check Entra ID role/group mappings.");
      } else {
        setStatus("Failed to load trust state.");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role !== "admin") return;
    void load(false);
  }, [role, load]);

  useEffect(() => {
    if (role !== "admin" || !autoRefresh) return;
    const interval = setInterval(() => {
      void load(true);
    }, pollMs);
    return () => clearInterval(interval);
  }, [autoRefresh, role, load]);

  useEffect(() => {
    if (!lastUpdatedAt) return;
    const interval = setInterval(() => {
      setRefreshTick((t) => t + 1);
    }, 5000);
    return () => clearInterval(interval);
  }, [lastUpdatedAt]);

  if (role !== "admin") return null;

  return (
    <div className="panel">
      <h2>Trust Dashboard</h2>

      <div className="button-row" style={{ alignItems: "center", marginBottom: 8 }}>
        <button onClick={() => void load(false)} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <button className="btn-secondary" onClick={() => setAutoRefresh((v) => !v)}>
          Auto Refresh: {autoRefresh ? "ON" : "OFF"}
        </button>
        <span className="muted-text" style={{ fontSize: 12 }}>
          Freshness: {freshness}
        </span>
      </div>

      {status && <div className="console-box">{status}</div>}

      {data && (
        <div className="console-box">
          <div>
            <strong>Ledger Valid:</strong> {data.valid ? "Yes" : "No"}
          </div>

          <div>
            <strong>Record Count:</strong> {data.records}
          </div>

          <div>
            <strong>Ledger Root:</strong> {data.ledger_root}
          </div>

          <div>
            <strong>Frozen:</strong> {data.frozen ? "Yes" : "No"}
          </div>
        </div>
      )}
    </div>
  );
}
