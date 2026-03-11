import { useState } from "react";
import { runGovernanceDecision } from "./api";
import type { LlmProvider } from "./App";

interface Props {
  role: string;
  llmProvider: LlmProvider;
  onExecutionComplete: (executionId: string) => void;
}

export default function GovernedCtoStrategy({ role, llmProvider, onExecutionComplete }: Props) {
  const [reasoningLevel, setReasoningLevel] = useState("R2");
  const [policyLevel, setPolicyLevel] = useState("P1");
  const [status, setStatus] = useState("");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [packHash, setPackHash] = useState<string | null>(null);
  const [ledgerRoot, setLedgerRoot] = useState<string | null>(null);

  async function execute() {
    try {
      setStatus("Executing governance contract...");

      const response = await runGovernanceDecision({
        provider: llmProvider,
        reasoning_level: reasoningLevel,
        policy_level: policyLevel,
      });

      const state = response.execution_state;
      setExecutionId(state.execution_id);
      setPackHash(state.pack_hash);
      setLedgerRoot(state.ledger_root);
      onExecutionComplete(state.execution_id);
      setStatus("Governance execution complete.");
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes("No human intent found")) {
        setStatus("Execution blocked: submit Human Input first, then run governance execution.");
      } else {
        setStatus("Execution failed.");
      }
    }
  }

  return (
    <div className="panel">
      <h2>Exploratory Decision Draft (Non-Deterministic)</h2>
      <p className="muted-text">Provider: <strong>{llmProvider}</strong></p>

      {role === "admin" && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <label>Reasoning Level:</label>
              <select value={reasoningLevel} onChange={(e) => setReasoningLevel(e.target.value)}>
                <option value="R0">R0 - Executive Only</option>
                <option value="R1">R1 - Structured</option>
                <option value="R2">R2 - Analytical</option>
                <option value="R3">R3 - Strategic</option>
                <option value="R4">R4 - Scenario</option>
                <option value="R5">R5 - Adversarial Deep</option>
              </select>
            </div>
            <div>
              <label>Policy Level:</label>
              <select value={policyLevel} onChange={(e) => setPolicyLevel(e.target.value)}>
                <option value="P0">P0 - Minimal</option>
                <option value="P1">P1 - Standard</option>
                <option value="P2">P2 - Enhanced</option>
                <option value="P3">P3 - Regulated</option>
                <option value="P4">P4 - High Assurance</option>
                <option value="P5">P5 - Critical Infrastructure</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <div className="button-row">
        <button className="btn-primary" onClick={() => void execute()}>Run Exploratory Draft</button>
      </div>

      {status && <div className="status">{status}</div>}

      {executionId && (
        <div className="metrics-grid" style={{ marginTop: 12 }}>
          <div className="metric-card"><h4>Execution ID</h4><p style={{ fontSize: 12 }}>{executionId}</p></div>
          <div className="metric-card"><h4>Pack Hash</h4><p style={{ fontSize: 12 }}>{packHash}</p></div>
          <div className="metric-card"><h4>Ledger Root</h4><p style={{ fontSize: 12 }}>{ledgerRoot}</p></div>
        </div>
      )}
    </div>
  );
}
