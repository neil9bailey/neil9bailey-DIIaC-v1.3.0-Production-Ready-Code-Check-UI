import { useState } from "react";
import { runGovernanceDecision } from "./api";
import type { LlmContribution } from "./api";
import type { LlmProvider } from "./App";

interface Props {
  role: string;
  llmProvider: LlmProvider;
  onExecutionComplete: (executionId: string) => void;
}

const REASONING_DESCRIPTIONS: Record<string, string> = {
  R0: "Executive summary only — high-level findings, no deep analysis",
  R1: "Structured breakdown — organised sections with key findings",
  R2: "Analytical — multi-factor analysis with supporting rationale",
  R3: "Strategic — scenario modelling and long-horizon considerations",
  R4: "Scenario planning — explicit alternative outcomes and risk modelling",
  R5: "Adversarial deep — red-team challenges and stress-test assumptions",
};

const POLICY_DESCRIPTIONS: Record<string, string> = {
  P0: "Minimal — basic guardrails only, fast execution",
  P1: "Standard — common governance controls applied",
  P2: "Enhanced — stricter policy evaluation with audit trail",
  P3: "Regulated — compliance-grade controls (financial, health)",
  P4: "High Assurance — national infrastructure or government grade",
  P5: "Critical Infrastructure — maximum policy rigor, dual-sign required",
};

export default function GovernedCtoStrategy({ role, llmProvider, onExecutionComplete }: Props) {
  const [reasoningLevel, setReasoningLevel] = useState("R2");
  const [policyLevel, setPolicyLevel] = useState("P1");
  const [status, setStatus] = useState("");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [packHash, setPackHash] = useState<string | null>(null);
  const [ledgerRoot, setLedgerRoot] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [llmContributions, setLlmContributions] = useState<{ chatgpt: LlmContribution | null; copilot: LlmContribution | null } | null>(null);

  async function execute() {
    try {
      setRunning(true);
      setLlmContributions(null);
      setStatus("Executing governance contract…");
      const response = await runGovernanceDecision({ provider: llmProvider, reasoning_level: reasoningLevel, policy_level: policyLevel });
      const state = response.execution_state;
      setExecutionId(state.execution_id);
      setPackHash(state.pack_hash);
      setLedgerRoot(state.ledger_root);
      if (state.llm_contributions) setLlmContributions(state.llm_contributions);
      onExecutionComplete(state.execution_id);
      setStatus("✔ Governance execution complete. Decision pack signed and recorded.");
    } catch (err: unknown) {
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("No human intent found")) {
        setStatus("⚠ Execution blocked — submit Human Intent (Step 1) before running governance execution.");
      } else {
        setStatus("Execution failed. Verify the bridge service is running and retry.");
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: "0 0 3px" }}>Step 2 — Exploratory Decision Draft</h2>
          <p className="muted-text" style={{ margin: 0 }}>
            Non-deterministic AI-assisted analysis governed by policy and reasoning constraints.
            Provider: <strong style={{ color: "var(--navy-700)" }}>{llmProvider}</strong>
          </p>
        </div>
        <span style={{ background: "var(--amber-50)", color: "var(--amber-700)", border: "1px solid var(--amber-100)", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, flexShrink: 0, marginLeft: 16 }}>
          Non-Deterministic
        </span>
      </div>

      {role === "admin" && (
        <div className="form-section">
          <div className="form-section-header">
            <span className="form-section-title">Governance Parameters</span>
            <span className="form-section-desc">Admin controls — affects analysis depth and policy strictness</span>
          </div>
          <div className="form-section-body">
            <div className="form-grid-2">
              <div className="form-field">
                <label>Reasoning Level</label>
                <select value={reasoningLevel} onChange={(e) => setReasoningLevel(e.target.value)}>
                  {Object.keys(REASONING_DESCRIPTIONS).map(r => (
                    <option key={r} value={r}>{r} — {REASONING_DESCRIPTIONS[r].split("—")[0].trim()}</option>
                  ))}
                </select>
                <div className="field-hint">{REASONING_DESCRIPTIONS[reasoningLevel]}</div>
              </div>
              <div className="form-field">
                <label>Policy Level</label>
                <select value={policyLevel} onChange={(e) => setPolicyLevel(e.target.value)}>
                  {Object.keys(POLICY_DESCRIPTIONS).map(p => (
                    <option key={p} value={p}>{p} — {POLICY_DESCRIPTIONS[p].split("—")[0].trim()}</option>
                  ))}
                </select>
                <div className="field-hint">{POLICY_DESCRIPTIONS[policyLevel]}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {(role === "standard" || role === "viewer") && (
        <div style={{ background: "var(--slate-50)", border: "1px solid var(--slate-200)", borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 12, color: "var(--slate-500)" }}>
          Running with default parameters: <strong>R2 (Analytical)</strong> reasoning · <strong>P1 (Standard)</strong> policy
        </div>
      )}

      <div className="button-row">
        <button className="btn-primary" onClick={() => void execute()} disabled={running}>
          {running ? "Executing…" : "Run Exploratory Draft"}
        </button>
      </div>

      {status && (
        <div
          className="status"
          style={
            status.startsWith("✔") ? { background: "var(--green-50)", color: "var(--green-700)", borderLeftColor: "var(--green-600)" }
            : status.startsWith("⚠") ? { background: "var(--amber-50)", color: "var(--amber-700)", borderLeftColor: "var(--amber-600)" }
            : {}
          }
        >
          {status}
        </div>
      )}

      {executionId && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--slate-400)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            Execution Result
          </div>
          <div className="ledger-grid">
            <div className="ledger-card">
              <div className="ledger-card-label">Execution ID</div>
              <div className="ledger-card-value">{executionId}</div>
            </div>
            <div className="ledger-card">
              <div className="ledger-card-label">Pack Hash</div>
              <div className="ledger-card-value">{packHash ?? "—"}</div>
            </div>
            <div className="ledger-card">
              <div className="ledger-card-label">Ledger Root</div>
              <div className="ledger-card-value">{ledgerRoot ?? "—"}</div>
            </div>
          </div>

          {llmContributions && (llmContributions.chatgpt || llmContributions.copilot) && (
            <div style={{ marginTop: 14, background: "var(--green-50, #f0fdf4)", border: "1px solid var(--green-200, #bbf7d0)", borderRadius: 8, padding: "12px 16px" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--green-700, #15803d)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>
                Dual LLM Loop — Evidence of Participation
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {llmContributions.chatgpt && (
                  <div style={{ background: "white", border: "1px solid var(--green-200, #bbf7d0)", borderRadius: 6, padding: "10px 12px" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--navy-800)", marginBottom: 6 }}>ChatGPT — Strategy Synthesis</div>
                    <div style={{ fontSize: 11, color: "var(--slate-500)", marginBottom: 3 }}>Model: <strong>{llmContributions.chatgpt.model}</strong></div>
                    <div style={{ fontSize: 11, color: "var(--slate-500)", marginBottom: 3 }}>Sections generated: <strong>{llmContributions.chatgpt.sections.length}</strong></div>
                    <div style={{ fontSize: 10, color: "var(--slate-400)", fontFamily: "var(--font-mono)" }}>{llmContributions.chatgpt.sections.join(", ")}</div>
                    <div style={{ fontSize: 10, color: "var(--green-600, #16a34a)", marginTop: 4 }}>Called at: {new Date(llmContributions.chatgpt.called_at).toLocaleTimeString()}</div>
                  </div>
                )}
                {llmContributions.copilot && (
                  <div style={{ background: "white", border: "1px solid var(--green-200, #bbf7d0)", borderRadius: 6, padding: "10px 12px" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--navy-800)", marginBottom: 6 }}>Copilot — Red Team Challenge</div>
                    <div style={{ fontSize: 11, color: "var(--slate-500)", marginBottom: 3 }}>Model: <strong>{llmContributions.copilot.model}</strong></div>
                    <div style={{ fontSize: 11, color: "var(--slate-500)", marginBottom: 3 }}>Sections generated: <strong>{llmContributions.copilot.sections.length}</strong></div>
                    <div style={{ fontSize: 10, color: "var(--slate-400)", fontFamily: "var(--font-mono)" }}>{llmContributions.copilot.sections.join(", ")}</div>
                    <div style={{ fontSize: 10, color: "var(--green-600, #16a34a)", marginTop: 4 }}>Called at: {new Date(llmContributions.copilot.called_at).toLocaleTimeString()}</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
