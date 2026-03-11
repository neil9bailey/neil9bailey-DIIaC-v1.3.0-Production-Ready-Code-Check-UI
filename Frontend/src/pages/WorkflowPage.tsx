import { useAppContext } from "../AppContext";
import HumanInputPanel from "../HumanInputPanel";
import GovernedCtoStrategy from "../GovernedCtoStrategy";
import GovernedReportViewer from "../GovernedReportViewer";

export default function WorkflowPage() {
  const { role, llmProvider, latestExecutionId, setLatestExecutionId } = useAppContext();
  const isAdmin = role === "admin";

  const step1Done = false; // intent is stateless per execution
  const step2Done = !!latestExecutionId;
  const step3Done = false;

  return (
    <div>
      {/* Workflow step indicator */}
      <div className="workflow-steps">
        <div className={`workflow-step ${!step2Done ? "step-active" : "step-done"}`}>
          <div className="step-num">{step2Done ? "✓" : "1"}</div>
          <div>
            <div style={{ fontWeight: 600 }}>Submit Intent</div>
            <div style={{ fontSize: 11, opacity: 0.75 }}>Enter strategic objective</div>
          </div>
        </div>
        <div className={`workflow-step ${step2Done && !step3Done ? "step-active" : step3Done ? "step-done" : ""}`}>
          <div className="step-num">{step3Done ? "✓" : "2"}</div>
          <div>
            <div style={{ fontWeight: 600 }}>Governance Draft</div>
            <div style={{ fontSize: 11, opacity: 0.75 }}>Run exploratory decision</div>
          </div>
        </div>
        <div className={`workflow-step ${step2Done ? "step-active" : ""}`}>
          <div className="step-num">3</div>
          <div>
            <div style={{ fontWeight: 600 }}>Export Artifacts</div>
            <div style={{ fontSize: 11, opacity: 0.75 }}>Download decision pack</div>
          </div>
        </div>
      </div>

      {/* Step 1: Human Intent — shown to non-admins; admins can also use it */}
      {!isAdmin && <HumanInputPanel />}
      {isAdmin && (
        <details open>
          <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--navy-700)", padding: "10px 0", marginBottom: 4 }}>
            Step 1 — Submit Human Intent (optional for admins using Decision Evidence Workspace)
          </summary>
          <HumanInputPanel />
        </details>
      )}

      {/* Step 2: Exploratory Decision Draft */}
      <GovernedCtoStrategy
        role={role}
        llmProvider={llmProvider}
        onExecutionComplete={setLatestExecutionId}
      />

      {/* Step 3: Export Dashboard */}
      {latestExecutionId ? (
        <GovernedReportViewer executionId={latestExecutionId} />
      ) : (
        <div className="panel" style={{ background: "var(--slate-50)", borderStyle: "dashed", textAlign: "center", color: "var(--slate-400)", padding: "32px 24px" }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>📂</div>
          <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--slate-500)" }}>No Execution Yet</div>
          <div style={{ fontSize: 12 }}>Run an exploratory governance draft above to generate artifacts here.</div>
        </div>
      )}
    </div>
  );
}
