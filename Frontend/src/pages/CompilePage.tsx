import { useAppContext } from "../AppContext";
import MultiRoleGovernedCompilePanel from "../MultiRoleGovernedCompilePanel";
import GovernedReportViewer from "../GovernedReportViewer";

export default function CompilePage() {
  const { role, llmProvider, latestExecutionId, setLatestExecutionId } = useAppContext();

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
      <div className="governance-notice">
        <strong>Production Workflow</strong> — This workspace collects multi-role evidence and runs a
        deterministic governed compile. All outputs are cryptographically signed and recorded in the audit ledger.
        Use the <strong>Governance Workflow</strong> page for exploratory drafts.
      </div>

      <MultiRoleGovernedCompilePanel
        role={role}
        llmProvider={llmProvider}
        onExecutionComplete={setLatestExecutionId}
      />

      {/* Report viewer shows the latest compile output */}
      {latestExecutionId ? (
        <GovernedReportViewer executionId={latestExecutionId} />
      ) : (
        <div className="panel" style={{ background: "var(--slate-50)", borderStyle: "dashed", textAlign: "center", color: "var(--slate-400)", padding: "28px 24px" }}>
          <div style={{ fontSize: 22, marginBottom: 8 }}>📋</div>
          <div style={{ fontWeight: 600, color: "var(--slate-500)", marginBottom: 4 }}>No Compile Output Yet</div>
          <div style={{ fontSize: 12 }}>Complete the evidence workspace above and run a governed compile to see reports here.</div>
        </div>
      )}
    </div>
  );
}
