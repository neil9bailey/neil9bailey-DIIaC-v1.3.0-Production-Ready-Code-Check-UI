import { useAppContext } from "../AppContext";
import TrustDashboard from "../TrustDashboard";
import ImpactViewer from "../ImpactViewer";
import AdminConsolePanel from "../AdminConsolePanel";

export default function AdminPage() {
  const { role, latestExecutionId } = useAppContext();

  if (role !== "admin") {
    return (
      <div className="panel" style={{ textAlign: "center", padding: "40px 24px", color: "var(--slate-400)" }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
        <div style={{ fontWeight: 600, color: "var(--slate-500)", marginBottom: 4 }}>Admin Access Required</div>
        <div style={{ fontSize: 12 }}>This page is only accessible to administrators.</div>
      </div>
    );
  }

  return (
    <div>
      {/* Trust Ledger + Policy Impact side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 0 }}>
        <TrustDashboard role={role} />
        <ImpactViewer role={role} />
      </div>

      {/* Full-width Admin Console */}
      <AdminConsolePanel role={role} executionId={latestExecutionId} />
    </div>
  );
}
