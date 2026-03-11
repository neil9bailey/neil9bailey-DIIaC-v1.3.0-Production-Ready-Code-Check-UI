import { useEffect, useMemo, useState } from "react";
import { createHumanInput, type BusinessProfileEntry, listBusinessProfiles, runLlmGovernedCompile, submitRoleInput } from "./api";

interface Props {
  role: string;
  onExecutionComplete: (executionId: string) => void;
}

export default function MultiRoleGovernedCompilePanel({ role, onExecutionComplete }: Props) {
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

  useEffect(() => {
    if (role !== "admin") return;
    listBusinessProfiles()
      .then((res) => {
        const loadedProfiles = (res.profiles || []).filter((p): p is BusinessProfileEntry => Boolean(p));
        setProfiles(loadedProfiles);
        const profileIds = loadedProfiles
          .map((p) => p.profile_id || p.file || "")
          .filter((p): p is string => Boolean(p));
        if (profileIds.length && !profileIds.includes(businessProfile)) {
          setBusinessProfile(profileIds[0]);
        }
      })
      .catch((err: unknown) => {
        console.error(err);
        setStatus("Failed to load business profiles");
      });
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
    return value
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
  }

  function generateContextIdFromRole(): void {
    const domainPart = normalizeContextId(domain || "decision");
    const rolePart = normalizeContextId(selectedRole || "role");
    setExecutionContextId(`ctx-${domainPart}-${rolePart}`);
  }

  function toggleGovernanceMode(mode: string): void {
    setGovernanceModes((prev: string[]) => (prev.includes(mode) ? prev.filter((m: string) => m !== mode) : [...prev, mode]));
  }

  async function submitRole() {
    try {
      setStatus("Submitting role input...");
      if (humanIntent.trim()) {
        await createHumanInput({ raw_text: humanIntent.trim() });
      }
      await submitRoleInput({
        execution_context_id: executionContextId,
        role: selectedRole,
        domain,
        assertions: [assertion],
        non_negotiables: ["privacy-by-design"],
        risk_flags: ["vendor-lockin"],
        evidence_refs: [`${selectedRole}-evidence-1`],
      });
      setStatus("Role input submitted.");
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to submit role input");
    }
  }

  async function runCompile() {
    try {
      setStatus("Running deterministic LLM + governed compile...");
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
        provider: "ChatGPT",
        human_intent: humanIntent,
      });

      const executionId = response.compile?.execution_id || response.compile?.execution_state?.execution_id;
      if (executionId) {
        onExecutionComplete(executionId);
        const decisionStatus = response.compile?.decision_summary?.decision_status;
        setStatus(
          decisionStatus === "not_recommended"
            ? `Compile complete: ${executionId} (Decision NOT recommended — see report rationale)`
            : `Deterministic compile complete: ${executionId}`,
        );
      } else {
        setStatus("Compile returned without execution ID.");
      }
    } catch (err: unknown) {
      console.error(err);
      setStatus("Governed compile failed");
    }
  }

  return (
    <div className="panel">
      <h2>Decision Evidence Workspace (Production)</h2>
      <p>
        Use this as the primary production workflow: human intent + role evidence + deterministic governed compile.
      </p>

      <div>
        <label>Human Intent:</label>
        <textarea
          rows={4}
          value={humanIntent}
          onChange={(e) => setHumanIntent(e.target.value)}
          placeholder="Describe the decision objective, constraints, and expected outcomes."
          style={{ width: "100%" }}
        />
      </div>

      <div>
        <label>Execution Context ID:</label>
        <input value={executionContextId} onChange={(e) => setExecutionContextId(normalizeContextId(e.target.value))} />
        <small>Format: <code>ctx-&lt;domain&gt;-&lt;role&gt;</code> (lowercase, numbers, hyphens). Reuse the same ID to aggregate multi-role evidence for one decision run.</small>
        <div className="button-row" style={{ marginTop: 8 }}>
          <button type="button" className="btn-secondary" onClick={generateContextIdFromRole}>Generate from role/domain</button>
        </div>
      </div>

      <div>
        <label>Role:</label>
        <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
          <option value="IT_SECTOR_LEAD">IT_SECTOR_LEAD</option>
          <option value="ACTING_CTO">ACTING_CTO</option>
          <option value="ENTERPRISE_ARCHITECT">ENTERPRISE_ARCHITECT</option>
          <option value="PRINCIPAL_ENGINEER">PRINCIPAL_ENGINEER</option>
          <option value="CIO">CIO</option>
          <option value="CSO">CSO</option>
        </select>
      </div>

      <div>
        <label>Domain (free text):</label>
        <input value={domain} onChange={(e) => setDomain(e.target.value)} />
        <small>Use a concise area label (for example: network-transformation, cyber-risk, data-platform).</small>
      </div>

      <div>
        <label>Assertion (free text):</label>
        <input value={assertion} onChange={(e) => setAssertion(e.target.value)} />
        <small>State the key claim or recommendation this role is asserting with evidence.</small>
      </div>

      <button onClick={() => void submitRole()}>Submit Role Input</button>

      <hr />

      <div>
        <label>Business Profile:</label>
        <select value={businessProfile} onChange={(e) => setBusinessProfile(e.target.value)}>
          {(profiles.length ? profiles.map((p) => p.profile_id || p.file || "") : [businessProfile]).map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div>
        <label>Schema:</label>
        <select value={effectiveSchemaId} onChange={(e) => setSchemaId(e.target.value)}>
          {schemaOptions.map((schema) => (
            <option key={schema} value={schema}>{schema}</option>
          ))}
        </select>
      </div>

      <div>
        <label>Reasoning Level:</label>
        <select value={reasoningLevel} onChange={(e) => setReasoningLevel(e.target.value)}>
          <option value="R2">R2</option>
          <option value="R3">R3</option>
          <option value="R4">R4</option>
          <option value="R5">R5</option>
        </select>
      </div>

      <div>
        <label>Policy Level:</label>
        <select value={policyLevel} onChange={(e) => setPolicyLevel(e.target.value)}>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
          <option value="P4">P4</option>
          <option value="P5">P5</option>
        </select>
      </div>

      <div>
        <label>Governance Modes:</label>
        <div className="button-row">
          {["FIRST-PRINCIPLES MODE", "DEVIL'S ADVOCATE MODE", "CONSTRAINTS-FIRST MODE", "/deepresearch"].map((mode) => (
            <label key={mode} style={{ marginRight: 12 }}>
              <input
                type="checkbox"
                checked={governanceModes.includes(mode)}
                onChange={() => toggleGovernanceMode(mode)}
              /> {mode}
            </label>
          ))}
        </div>
        <small>These modes are passed as structured <code>governance_modes[]</code> controls into deterministic compile.</small>
      </div>

      <button onClick={() => void runCompile()}>Run Governed Compile</button>

      {status && <div className="status">{status}</div>}
    </div>
  );
}
