import { useEffect, useMemo, useState } from "react";
import { createHumanInput, type BusinessProfileEntry, listBusinessProfiles, runLlmGovernedCompile, submitRoleInput } from "./api";
import type { LlmProvider } from "./App";

interface Props {
  role: string;
  llmProvider: LlmProvider;
  onExecutionComplete: (executionId: string) => void;
}

const GOVERNANCE_MODE_INFO: Record<string, { label: string; desc: string }> = {
  "FIRST-PRINCIPLES MODE": { label: "First Principles", desc: "Deconstruct assumptions; reason from fundamentals up" },
  "DEVIL'S ADVOCATE MODE": { label: "Devil's Advocate", desc: "Challenge every claim with counterarguments" },
  "CONSTRAINTS-FIRST MODE": { label: "Constraints First", desc: "Lead with non-negotiables before exploring solutions" },
  "/deepresearch": { label: "Deep Research", desc: "Extended reasoning with multi-source evidence synthesis" },
};

export default function MultiRoleGovernedCompilePanel({ role, llmProvider, onExecutionComplete }: Props) {
  const [executionContextId, setExecutionContextId] = useState("ctx-ui");
  const [selectedRole, setSelectedRole] = useState("CIO");
  const [governanceModes, setGovernanceModes] = useState<string[]>([]);
  const [domain, setDomain] = useState("network-transformation");
  const [assertion, setAssertion] = useState("Adopt secure SD-WAN with measurable cost and resilience outcomes.");
  const [humanIntent, setHumanIntent] = useState("");
  const [businessProfile, setBusinessProfile] = useState("transport_profile_v1");
  const [profiles, setProfiles] = useState<BusinessProfileEntry[]>([]);
  const [schemaId, setSchemaId] = useState("GENERAL_SOLUTION_BOARD_REPORT_V1");
  const [reasoningLevel, setReasoningLevel] = useState("R5");
  const [policyLevel, setPolicyLevel] = useState("P3");
  const [status, setStatus] = useState("");
  const [roleSubmitted, setRoleSubmitted] = useState(false);

  useEffect(() => {
    if (role !== "admin") return;
    listBusinessProfiles()
      .then((res) => {
        const loadedProfiles = (res.profiles || []).filter((p): p is BusinessProfileEntry => Boolean(p));
        setProfiles(loadedProfiles);
        const profileIds = loadedProfiles.map((p) => p.profile_id || p.file || "").filter(Boolean);
        if (profileIds.length && !profileIds.includes(businessProfile)) setBusinessProfile(profileIds[0]);
      })
      .catch((err: unknown) => { console.error(err); setStatus("Failed to load business profiles"); });
  }, [role, businessProfile]);

  const selectedProfile = profiles.find((p) => (p.profile_id || p.file) === businessProfile);
  const schemaOptions = (selectedProfile?.allowed_schemas || ["GENERAL_SOLUTION_BOARD_REPORT_V1"]).filter(
    (s): s is string => typeof s === "string" && s.length > 0,
  );
  const effectiveSchemaId = useMemo(() => {
    if (!schemaOptions.length) return "";
    return schemaOptions.includes(schemaId) ? schemaId : schemaOptions[0];
  }, [schemaId, schemaOptions]);

  if (role !== "admin") return null;

  function normalizeContextId(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "").slice(0, 64);
  }

  function generateContextIdFromRole(): void {
    const domainPart = normalizeContextId(domain || "decision");
    const rolePart = normalizeContextId(selectedRole || "role");
    setExecutionContextId(`ctx-${domainPart}-${rolePart}`);
  }

  function toggleGovernanceMode(mode: string): void {
    setGovernanceModes((prev) => prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]);
  }

  async function submitRole() {
    try {
      setStatus("Submitting role evidence…");
      if (humanIntent.trim()) await createHumanInput({ raw_text: humanIntent.trim() });
      await submitRoleInput({
        execution_context_id: executionContextId,
        role: selectedRole,
        domain,
        assertions: [assertion],
        non_negotiables: ["privacy-by-design"],
        risk_flags: ["vendor-lockin"],
        evidence_refs: [`${selectedRole}-evidence-1`],
      });
      setRoleSubmitted(true);
      setStatus("✔ Role evidence submitted. You can add more roles or proceed to compile.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to submit role evidence.");
    }
  }

  async function runCompile() {
    try {
      setStatus("Running deterministic LLM-governed compile…");
      const response = await runLlmGovernedCompile({
        execution_context_id: executionContextId,
        schema_id: effectiveSchemaId,
        profile_id: businessProfile,
        reasoning_level: reasoningLevel,
        policy_level: policyLevel,
        role: selectedRole,
        domain,
        assertions: [assertion],
        governance_modes: governanceModes,
        provider: llmProvider,
        human_intent: humanIntent,
      });
      const executionId = response.compile?.execution_id || response.compile?.execution_state?.execution_id;
      if (executionId) {
        onExecutionComplete(executionId);
        const decisionStatus = response.compile?.decision_summary?.decision_status;
        setStatus(
          decisionStatus === "not_recommended"
            ? `✔ Compile complete: ${executionId} — Decision NOT recommended (see report rationale)`
            : `✔ Deterministic compile complete: ${executionId}`,
        );
      } else {
        setStatus("Compile returned without execution ID.");
      }
    } catch (err: unknown) {
      console.error(err);
      setStatus("Governed compile failed. Verify bridge service and retry.");
    }
  }

  return (
    <div className="panel">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <h2 style={{ margin: "0 0 3px" }}>Decision Evidence Workspace</h2>
          <p className="muted-text" style={{ margin: 0 }}>
            Production workflow: collect multi-role evidence → deterministic governed compile.
            Provider: <strong style={{ color: "var(--navy-700)" }}>{llmProvider}</strong>
          </p>
        </div>
        <span style={{ background: "var(--green-50)", color: "var(--green-700)", border: "1px solid var(--green-100)", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, flexShrink: 0, marginLeft: 16 }}>
          Deterministic
        </span>
      </div>

      {/* ── Section 1: Intent & Context ──────────────────────── */}
      <div className="form-section">
        <div className="form-section-header">
          <div className="form-section-number">1</div>
          <span className="form-section-title">Human Intent & Execution Context</span>
        </div>
        <div className="form-section-body">
          <div className="form-field" style={{ marginBottom: 14 }}>
            <label>Human Intent</label>
            <textarea
              rows={4}
              value={humanIntent}
              onChange={(e) => setHumanIntent(e.target.value)}
              placeholder="Describe the decision objective, constraints, regulatory context, and expected outcomes…"
              style={{ fontFamily: "var(--font-sans)" }}
            />
            <div className="field-hint">
              Example: "Evaluate migration of on-premises ERP to Azure Government Cloud under UK NCSC guidelines, with a £2M capex ceiling and 18-month delivery window."
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="form-field" style={{ flex: "1 1 280px" }}>
              <label>Execution Context ID</label>
              <input
                value={executionContextId}
                onChange={(e) => setExecutionContextId(normalizeContextId(e.target.value))}
                placeholder="ctx-domain-role"
              />
              <div className="field-hint">
                Format: <code style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>ctx-&lt;domain&gt;-&lt;role&gt;</code> — reuse to aggregate multi-role evidence into one decision
              </div>
            </div>
            <button type="button" className="btn-secondary" onClick={generateContextIdFromRole} style={{ marginBottom: 20 }}>
              Auto-Generate
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 2: Role & Domain ─────────────────────────── */}
      <div className="form-section">
        <div className="form-section-header">
          <div className="form-section-number">2</div>
          <span className="form-section-title">Role & Domain Configuration</span>
          <span className="form-section-desc">Submit one role at a time; multiple submissions aggregate evidence</span>
        </div>
        <div className="form-section-body">
          <div className="form-grid-2" style={{ marginBottom: 14 }}>
            <div className="form-field">
              <label>Submitting Role</label>
              <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
                <option value="CIO">CIO — Chief Information Officer</option>
                <option value="CSO">CSO — Chief Security Officer</option>
                <option value="ACTING_CTO">ACTING_CTO — Acting CTO</option>
                <option value="IT_SECTOR_LEAD">IT_SECTOR_LEAD — Sector Lead</option>
                <option value="ENTERPRISE_ARCHITECT">ENTERPRISE_ARCHITECT — Enterprise Architect</option>
                <option value="PRINCIPAL_ENGINEER">PRINCIPAL_ENGINEER — Principal Engineer</option>
              </select>
              <div className="field-hint">The organisational role providing this evidence submission</div>
            </div>
            <div className="form-field">
              <label>Decision Domain</label>
              <input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g. network-transformation"
              />
              <div className="field-hint">
                Examples: <span style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>network-transformation · cloud-migration · ai-governance · security-posture</span>
              </div>
            </div>
          </div>
          <div className="form-field">
            <label>Role Assertion</label>
            <input
              value={assertion}
              onChange={(e) => setAssertion(e.target.value)}
              placeholder="State the key recommendation or finding from this role's perspective…"
            />
            <div className="field-hint">
              The specific claim or recommendation this role is asserting, backed by their evidence and professional judgement.
              Example: <em>"Adopt secure SD-WAN with measurable cost and resilience SLAs; phased 12-month rollout with reversibility gates."</em>
            </div>
          </div>
          <div className="button-row" style={{ marginTop: 14 }}>
            <button className="btn-secondary" onClick={() => void submitRole()}>
              Submit Role Evidence
            </button>
            {roleSubmitted && (
              <span style={{ fontSize: 12, color: "var(--green-600)", fontWeight: 600, alignSelf: "center" }}>
                ✔ Evidence submitted — add another role or proceed to compile
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Section 3: Compile Configuration ────────────────── */}
      <div className="form-section">
        <div className="form-section-header">
          <div className="form-section-number">3</div>
          <span className="form-section-title">Compile Configuration</span>
          <span className="form-section-desc">Business profile, schema, reasoning depth, and policy level</span>
        </div>
        <div className="form-section-body">
          <div className="form-grid-2" style={{ marginBottom: 14 }}>
            <div className="form-field">
              <label>Business Profile</label>
              <select value={businessProfile} onChange={(e) => setBusinessProfile(e.target.value)}>
                {(profiles.length ? profiles.map((p) => p.profile_id || p.file || "") : [businessProfile]).map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
              <div className="field-hint">Defines industry-specific policy constraints and compliance frameworks</div>
            </div>
            <div className="form-field">
              <label>Output Schema</label>
              <select value={effectiveSchemaId} onChange={(e) => setSchemaId(e.target.value)}>
                {schemaOptions.map((schema) => <option key={schema} value={schema}>{schema}</option>)}
              </select>
              <div className="field-hint">Determines the structure and sections of the output governance report</div>
            </div>
          </div>
          <div className="form-grid-2">
            <div className="form-field">
              <label>Reasoning Level</label>
              <select value={reasoningLevel} onChange={(e) => setReasoningLevel(e.target.value)}>
                <option value="R2">R2 — Analytical</option>
                <option value="R3">R3 — Strategic</option>
                <option value="R4">R4 — Scenario Planning</option>
                <option value="R5">R5 — Adversarial Deep</option>
              </select>
              <div className="field-hint">R5 recommended for production decisions; increases LLM reasoning depth</div>
            </div>
            <div className="form-field">
              <label>Policy Level</label>
              <select value={policyLevel} onChange={(e) => setPolicyLevel(e.target.value)}>
                <option value="P1">P1 — Standard</option>
                <option value="P2">P2 — Enhanced</option>
                <option value="P3">P3 — Regulated</option>
                <option value="P4">P4 — High Assurance</option>
                <option value="P5">P5 — Critical Infrastructure</option>
              </select>
              <div className="field-hint">P3+ enforces compliance-grade audit controls and stricter output evaluation</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 4: Governance Modes ──────────────────────── */}
      <div className="form-section">
        <div className="form-section-header">
          <div className="form-section-number">4</div>
          <span className="form-section-title">Governance Modes</span>
          <span className="form-section-desc">Optional — select one or more analytical lenses</span>
        </div>
        <div className="form-section-body">
          <div className="gov-mode-grid">
            {Object.entries(GOVERNANCE_MODE_INFO).map(([mode, info]) => (
              <label
                key={mode}
                className={`gov-mode-option${governanceModes.includes(mode) ? " checked" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={governanceModes.includes(mode)}
                  onChange={() => toggleGovernanceMode(mode)}
                  style={{ flexShrink: 0 }}
                />
                <div>
                  <div className="gov-mode-name">{info.label}</div>
                  <div className="gov-mode-desc">{info.desc}</div>
                </div>
              </label>
            ))}
          </div>
          <div className="field-hint" style={{ marginTop: 8 }}>
            Selected modes are passed as structured governance controls into the deterministic compile pipeline.
          </div>
        </div>
      </div>

      {/* ── Run Compile ───────────────────────────────────────── */}
      <div className="button-row">
        <button className="btn-primary" style={{ padding: "9px 24px" }} onClick={() => void runCompile()}>
          ▶ Run Governed Compile
        </button>
      </div>

      {status && (
        <div
          className="status"
          style={
            status.startsWith("✔") ? { background: "var(--green-50)", color: "var(--green-700)", borderLeftColor: "var(--green-600)" }
            : status.includes("failed") || status.includes("Failed") ? { background: "var(--red-50)", color: "var(--red-700)", borderLeftColor: "var(--red-600)" }
            : {}
          }
        >
          {status}
        </div>
      )}
    </div>
  );
}
