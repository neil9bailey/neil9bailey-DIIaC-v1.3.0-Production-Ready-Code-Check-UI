import { useAppContext } from "../AppContext";
import OperationalDashboard from "../OperationalDashboard";

export default function DashboardPage() {
  const { role } = useAppContext();

  if (role !== "admin") {
    return (
      <div className="panel" style={{ textAlign: "center", padding: "40px 24px", color: "var(--slate-400)" }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>🔒</div>
        <div style={{ fontWeight: 600, color: "var(--slate-500)", marginBottom: 4 }}>Admin Access Required</div>
        <div style={{ fontSize: 12 }}>This page is only accessible to administrators.</div>
      </div>
    );
  }

  return <OperationalDashboard inline />;
}
