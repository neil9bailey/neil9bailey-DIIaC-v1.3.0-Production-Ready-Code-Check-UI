import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useAppContext } from "../AppContext";
import { fetchAdminHealth, fetchAdminMetrics, type AdminHealthResponse, type AdminMetricsResponse } from "../api";

function IconWorkflow() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
    </svg>
  );
}
function IconCompile() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16,18 22,12 16,6" /><polyline points="8,6 2,12 8,18" />
    </svg>
  );
}
function IconAdmin() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function IconDashboard() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

export default function HomePage() {
  const { role, llmProvider, latestExecutionId } = useAppContext();
  const isAdmin = role === "admin";
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);

  useEffect(() => {
    if (!isAdmin) return;
    fetchAdminHealth().then(setHealth).catch(() => {});
    fetchAdminMetrics().then(setMetrics).catch(() => {});
  }, [isAdmin]);

  return (
    <div>
      {/* Governance banner */}
      <div className="governance-banner">
        <div className="governance-banner-icon">🛡</div>
        <div>
          <div className="governance-banner-title">Governance Notice</div>
          <div className="governance-banner-text">
            AI-assisted content is treated as <strong style={{ color: "#e2e8f0" }}>untrusted input</strong>.
            All outputs are deterministically governed, policy-bound, and recorded in an immutable audit ledger.
            Every decision is cryptographically signed and reproducible.
          </div>
        </div>
      </div>

      {/* KPI row (admin only) */}
      {isAdmin && (
        <div className="kpi-row">
          <div className="kpi-card kpi-blue">
            <div className="kpi-value">{metrics?.executions_total ?? "—"}</div>
            <div className="kpi-label">Total Executions</div>
          </div>
          <div className="kpi-card kpi-green">
            <div className="kpi-value">{metrics?.signed_recent_executions ?? "—"}</div>
            <div className="kpi-label">Signed Recent</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-value">{metrics?.ledger_record_count ?? health?.ledger_record_count ?? "—"}</div>
            <div className="kpi-label">Ledger Records</div>
          </div>
          <div className={`kpi-card ${health?.status === "ok" ? "kpi-green" : "kpi-amber"}`}>
            <div className="kpi-value" style={{ fontSize: 18 }}>{health?.status?.toUpperCase() ?? "—"}</div>
            <div className="kpi-label">Runtime Health</div>
          </div>
        </div>
      )}

      {/* Active session info */}
      {latestExecutionId && (
        <div className="panel" style={{ background: "var(--green-50)", borderColor: "var(--green-100)", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <h3 style={{ color: "var(--green-700)", margin: "0 0 2px" }}>Active Execution</h3>
              <p style={{ margin: 0, fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--green-700)" }}>{latestExecutionId}</p>
            </div>
            <NavLink to="/workflow" className="btn-success" style={{ textDecoration: "none", padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
              View Reports →
            </NavLink>
          </div>
        </div>
      )}

      {/* Platform info + Active LLM */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 14, marginBottom: 20, alignItems: "start" }}>
        <div className="panel" style={{ margin: 0 }}>
          <h2 style={{ marginBottom: 10 }}>About DIIaC</h2>
          <p style={{ margin: "0 0 10px", fontSize: 13, color: "var(--slate-600)", lineHeight: 1.65 }}>
            <strong>Decision Intelligence Infrastructure as Code</strong> (DIIaC) is an enterprise governance platform
            that bridges human strategic intent with deterministic, policy-governed AI outputs.
            Every execution produces a cryptographically-signed decision pack recorded in an immutable audit ledger.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["Deterministic Governance", "Policy-Bound", "Audit Ledger", "Multi-Role Evidence", "EU AI Act Ready"].map(t => (
              <span key={t} style={{ background: "var(--blue-50)", color: "var(--blue-600)", border: "1px solid var(--blue-100)", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 600 }}>{t}</span>
            ))}
          </div>
        </div>
        <div className="panel" style={{ margin: 0, minWidth: 160, textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "var(--slate-400)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>Active LLM</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: "var(--navy-900)" }}>{llmProvider}</div>
          <div style={{ fontSize: 11, color: "var(--slate-400)", marginTop: 4 }}>Change in sidebar</div>
        </div>
      </div>

      {/* Quick action cards */}
      <h3 style={{ margin: "0 0 14px", fontSize: 14, fontWeight: 700, color: "var(--navy-800)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Quick Actions
      </h3>
      <div className="action-grid">
        <NavLink to="/workflow" className="action-card">
          <div className="action-card-icon blue"><IconWorkflow /></div>
          <div className="action-card-title">Governance Workflow</div>
          <div className="action-card-desc">Submit human intent, run exploratory decision draft, and export governed artifacts.</div>
          <div className="action-card-arrow">Start workflow →</div>
        </NavLink>

        {isAdmin && (
          <NavLink to="/compile" className="action-card">
            <div className="action-card-icon green"><IconCompile /></div>
            <div className="action-card-title">Decision Evidence Workspace</div>
            <div className="action-card-desc">Collect multi-role evidence and run production deterministic governed compile.</div>
            <div className="action-card-arrow">Open workspace →</div>
          </NavLink>
        )}

        {isAdmin && (
          <NavLink to="/admin" className="action-card">
            <div className="action-card-icon navy"><IconAdmin /></div>
            <div className="action-card-title">Admin Console</div>
            <div className="action-card-desc">Service health monitoring, audit exports, execution logs, and database operations.</div>
            <div className="action-card-arrow">Open console →</div>
          </NavLink>
        )}

        {isAdmin && (
          <NavLink to="/dashboard" className="action-card">
            <div className="action-card-icon amber"><IconDashboard /></div>
            <div className="action-card-title">Operational Dashboard</div>
            <div className="action-card-desc">Real-time integration health, governance trends, and pending approval queue.</div>
            <div className="action-card-arrow">View dashboard →</div>
          </NavLink>
        )}
      </div>

      {/* Workflow overview */}
      <div className="panel" style={{ marginTop: 8 }}>
        <h3 style={{ margin: "0 0 16px" }}>Platform Workflow</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          {[
            { num: "1", title: "Submit Intent", desc: "Capture strategic objective or board directive as free-form human intent.", color: "var(--blue-600)" },
            { num: "2", title: "Governance Decision", desc: "LLM-assisted exploratory draft executed under policy and reasoning constraints.", color: "var(--blue-500)" },
            { num: "3", title: "Export Artifacts", desc: "Download decision pack — reports, evidence chain, policy evaluation.", color: "var(--green-600)" },
            { num: "4", title: isAdmin ? "Production Compile" : "Audit Trail", desc: isAdmin ? "Admin runs deterministic multi-role governed compile with full evidence." : "Every output cryptographically signed and recorded in immutable ledger.", color: isAdmin ? "var(--navy-700)" : "var(--slate-500)" },
          ].map(step => (
            <div key={step.num} style={{ padding: "14px 16px", background: "var(--slate-50)", borderRadius: 8, border: "1px solid var(--slate-200)" }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", background: step.color, color: "white", fontSize: 13, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 8 }}>{step.num}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--navy-900)", marginBottom: 4 }}>{step.title}</div>
              <div style={{ fontSize: 12, color: "var(--slate-500)", lineHeight: 1.5 }}>{step.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
