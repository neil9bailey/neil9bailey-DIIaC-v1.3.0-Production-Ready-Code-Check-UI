import { useEffect, useMemo, useState } from "react";
import { createHumanInput, type BusinessProfileEntry, listBusinessProfiles, runLlmGovernedCompile, submitRoleInput } from "./api";
import type { LlmProvider } from "./App";

interface Props {
  role: string;
  llmProvider: LlmProvider;
  onExecutionComplete: (executionId: string) => void;
}

export default function MultiRoleGovernedCompilePanel({ role, llmProvider, onExecutionComplete }: Props) {
  const requiredGovernanceModes = ["FIRST-PRINCIPLES MODE", "DEVIL'S ADVOCATE MODE", "CONSTRAINTS-FIRST MODE"];
  const [executionContextId, setExecutionContextId] = useState("ctx-ui");
  const [selectedRole, setSelectedRole] = useState("CIO");
  const [governanceModes, setGovernanceModes] = useState<string[]>(requiredGovernanceModes);
  const [domain, setDomain] = useState("network-transformation");
  const [assertion, setAssertion] = useState("Adopt secure SD-WAN with >=15% cycle-time reduction in <=6 months.");
  const [nonNegotiablesInput, setNonNegotiablesInput] = useState("Budget cap GBP 1.8M/year");
  const [riskFlagsInput, setRiskFlagsInput] = useState("vendor-lockin");
  const [goalsInput, setGoalsInput] = useState("Cycle-time reduction >=15%");
  const [regulatoryContextInput, setRegulatoryContextInput] = useState("GDPR, UK DPA 2018");
  const [successTargetsInput, setSuccessTargetsInput] = useState(">=15% cycle-time reduction; <=1% Sev1 increase");
  const [evidenceRefsInput, setEvidenceRefsInput] = useState(
    "https://www.fortinet.com/products/secure-sd-wan\nhttps://www.paloaltonetworks.com/sase/prisma-sd-wan",
  );
  const [humanIntent, setHumanIntent] = useState("");
  const [businessProfile, setBusinessProfile] = useState("it_enterprise_profile_v1");
  const [profiles, setProfiles] = useState<BusinessProfileEntry[]>([]);
  const [schemaId, setSchemaId] = useState("GENERAL_SOLUTION_BOARD_REPORT_V1");
  const [reasoningLevel, setReasoningLevel] = useState("R5");
  const [policyLevel, setPolicyLevel] = useState("P4");
  const [status, setStatus] = useState("");
  const [submittingRole, setSubmittingRole] = useState(false);
  const [runningCompile, setRunningCompile] = useState(false);

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
        const msg = err instanceof Error ? err.message : String(err);
        console.error(err);
        if (msg.includes("no_diiac_role") || msg.includes("403")) {
          setStatus("Access denied: DIIaC role not resolved. Check Entra ID role/group mappings.");
        } else {
          setStatus("Failed to load business profiles.");
        }
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
  const parsedEvidenceRefs = useMemo(() => parseEvidenceRefs(evidenceRefsInput), [evidenceRefsInput]);
  const strongEvidenceRefCount = useMemo(
    () => parsedEvidenceRefs.filter(isStrongEvidenceRef).length,
    [parsedEvidenceRefs],
  );

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
    setGovernanceModes((prev: string[]) => (prev.includes(mode) ? prev.filter((m: string) => m !== mode) : [...prev, mode]));
  }

  function buildRoleIdempotencyKey(): string {
    const evidenceRefs = parseEvidenceRefs(evidenceRefsInput);
    const seed = [
      normalizeContextId(executionContextId),
      normalizeContextId(selectedRole),
      normalizeContextId(domain),
      assertion.trim().toLowerCase(),
      evidenceRefs.sort().join("|").toLowerCase(),
    ].join("|");
    let hash = 2166136261;
    for (let i = 0; i < seed.length; i += 1) {
      hash ^= seed.charCodeAt(i);
      hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    const normalized = (hash >>> 0).toString(16).padStart(8, "0");
    return `role-${normalized}`;
  }

  function parseEvidenceRefs(value: string): string[] {
    return Array.from(
      new Set(
        value
          .split(/\r?\n|[,;]/)
          .map((v) => v.trim())
          .filter((v) => v.length > 0),
      ),
    );
  }

  function parseList(value: string): string[] {
    return Array.from(
      new Set(
        value
          .split(/\r?\n|[,;]/)
          .map((v) => v.trim())
          .filter((v) => v.length > 0),
      ),
    );
  }

  function isStrongEvidenceRef(ref: string): boolean {
    const lower = ref.toLowerCase();
    return (
      lower.startsWith("http://") ||
      lower.startsWith("https://") ||
      lower.startsWith("urn:") ||
      lower.startsWith("sha256:") ||
      lower.includes("/") ||
      lower.includes("\\") ||
      /\.(pdf|docx?|md|txt|json|xlsx?|csv)$/.test(lower)
    );
  }

  function buildEvidenceRefExamples(): string {
    const domainPart = normalizeContextId(domain || "decision");
    const rolePart = normalizeContextId(selectedRole || "role");
    const roleScopes: Record<string, string> = {
      CFO: "finance",
      CTO: "technology",
      CIO: "strategy",
      PROCUREMENT: "supplier",
      CSO: "security",
    };
    const roleScope = roleScopes[selectedRole] || rolePart;
    return [
      "https://www.fortinet.com/products/secure-sd-wan",
      "https://www.paloaltonetworks.com/sase/prisma-sd-wan",
      `urn:${roleScope}:board-paper:${domainPart}:2026-q1`,
      "sha256:3f1d0b0c5e6e0a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123",
    ].join("\n");
  }

  function fillExampleEvidenceRefs(): void {
    setEvidenceRefsInput(buildEvidenceRefExamples());
    setStatus("");
  }

  async function submitRole() {
    const evidenceRefs = parseEvidenceRefs(evidenceRefsInput);
    const strongRefs = evidenceRefs.filter(isStrongEvidenceRef);
    if (strongRefs.length < 2) {
      setStatus("At least 2 strong evidence refs are required (URI/document/hash).");
      return;
    }
    try {
      setSubmittingRole(true);
      setStatus("Submitting role input...");
      if (humanIntent.trim()) {
        await createHumanInput({ raw_text: humanIntent.trim() });
      }
      const roleResponse = await submitRoleInput({
        execution_context_id: executionContextId,
        role: selectedRole,
        domain,
        assertions: [assertion],
        non_negotiables: parseList(nonNegotiablesInput),
        risk_flags: parseList(riskFlagsInput),
        evidence_refs: evidenceRefs,
        idempotency_key: buildRoleIdempotencyKey(),
      });
      if (roleResponse.duplicate_ignored) {
        setStatus("Role input already exists for this context/role/assertion. Duplicate ignored.");
      } else {
        setStatus("Role input submitted.");
      }
    } catch (err: unknown) {
      console.error(err);
      setStatus("Failed to submit role input");
    } finally {
      setSubmittingRole(false);
    }
  }

  async function runCompile() {
    try {
      setRunningCompile(true);
      setStatus("Running deterministic LLM + governed compile...");
      const effectiveGovernanceModes = Array.from(new Set([...governanceModes, ...requiredGovernanceModes]));
      if (effectiveGovernanceModes.length !== governanceModes.length) {
        setGovernanceModes(effectiveGovernanceModes);
      }
      const response = await runLlmGovernedCompile({
        execution_context_id: executionContextId,
        schema_id: effectiveSchemaId,
        profile_id: businessProfile,
        reasoning_level: reasoningLevel,
        policy_level: policyLevel,
        role: selectedRole,
        domain,
        assertions: [assertion],
        non_negotiables: parseList(nonNegotiablesInput),
        risk_flags: parseList(riskFlagsInput),
        evidence_refs: parseEvidenceRefs(evidenceRefsInput),
        goals: parseList(goalsInput),
        regulatory_context: parseList(regulatoryContextInput),
        success_targets: parseList(successTargetsInput),
        governance_modes: effectiveGovernanceModes,
        provider: llmProvider,
        human_intent: humanIntent,
      });

      const executionId = response.compile?.execution_id || response.compile?.execution_state?.execution_id;
      if (executionId) {
        onExecutionComplete(executionId);
        const decisionStatus = response.compile?.decision_summary?.decision_status;
        setStatus(
          decisionStatus === "not_recommended"
            ? `Compile complete: ${executionId} (Decision NOT recommended - see report rationale)`
            : `Deterministic compile complete: ${executionId}`,
        );
      } else {
        setStatus("Compile returned without execution ID.");
      }
    } catch (err: unknown) {
      console.error(err);
      setStatus("Governed compile failed");
    } finally {
      setRunningCompile(false);
    }
  }

  return (
    <div className="panel">
      <h2>Decision Evidence Workspace (Production)</h2>
      <p className="muted-text">
        Primary production workflow: human intent + role evidence + deterministic governed compile.
        Provider: <strong>{llmProvider}</strong>
      </p>

      <div style={{ marginBottom: 12 }}>
        <label>Human Intent:</label>
        <textarea
          rows={3}
          value={humanIntent}
          onChange={(e) => setHumanIntent(e.target.value)}
          placeholder="Describe the decision objective, constraints, and expected outcomes."
        />
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
        <div style={{ flex: "1 1 260px" }}>
          <label>Execution Context ID:</label>
          <input value={executionContextId} onChange={(e) => setExecutionContextId(normalizeContextId(e.target.value))} style={{ width: "100%" }} />
          <small>Format: ctx-&lt;domain&gt;-&lt;role&gt;. Reuse to aggregate multi-role evidence.</small>
        </div>
        <button type="button" className="btn-secondary" onClick={generateContextIdFromRole}>Generate from role/domain</button>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 }}>
        <div>
          <label>Role:</label>
          <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)}>
            <option value="CIO">CIO</option>
            <option value="CTO">CTO</option>
            <option value="CFO">CFO</option>
            <option value="PROCUREMENT">PROCUREMENT</option>
            <option value="CSO">CSO</option>
            <option value="ENTERPRISE_ARCHITECT">ENTERPRISE_ARCHITECT</option>
            <option value="PRINCIPAL_ENGINEER">PRINCIPAL_ENGINEER</option>
            <option value="IT_SECTOR_LEAD">IT_SECTOR_LEAD</option>
          </select>
        </div>
        <div style={{ flex: "1 1 200px" }}>
          <label>Domain:</label>
          <input value={domain} onChange={(e) => setDomain(e.target.value)} style={{ width: "100%" }} />
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label>Assertion:</label>
        <input value={assertion} onChange={(e) => setAssertion(e.target.value)} style={{ width: "100%" }} />
        <small>State the key claim or recommendation this role is asserting with evidence.</small>
      </div>

      <div style={{ display: "grid", gap: 12, marginBottom: 12 }}>
        <div>
          <label>Non-Negotiables:</label>
          <input value={nonNegotiablesInput} onChange={(e) => setNonNegotiablesInput(e.target.value)} style={{ width: "100%" }} />
        </div>
        <div>
          <label>Risk Flags:</label>
          <input value={riskFlagsInput} onChange={(e) => setRiskFlagsInput(e.target.value)} style={{ width: "100%" }} />
        </div>
        <div>
          <label>Goals:</label>
          <input value={goalsInput} onChange={(e) => setGoalsInput(e.target.value)} style={{ width: "100%" }} />
        </div>
        <div>
          <label>Regulatory Context:</label>
          <input value={regulatoryContextInput} onChange={(e) => setRegulatoryContextInput(e.target.value)} style={{ width: "100%" }} />
        </div>
        <div>
          <label>Success Targets:</label>
          <input value={successTargetsInput} onChange={(e) => setSuccessTargetsInput(e.target.value)} style={{ width: "100%" }} />
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label>Evidence References:</label>
        <textarea
          rows={3}
          value={evidenceRefsInput}
          onChange={(e) => setEvidenceRefsInput(e.target.value)}
          placeholder="One per line (URI/document/hash). Minimum 2 strong refs."
        />
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="button" className="btn-secondary" onClick={fillExampleEvidenceRefs} disabled={submittingRole || runningCompile}>
            Fill Example Refs
          </button>
        </div>
        <small>Provide durable evidence refs (URI/document/hash). Minimum 2 strong refs required.</small>
        <br />
        <small style={{ color: strongEvidenceRefCount >= 2 ? "#166534" : "#b45309" }}>
          Strong refs detected: <strong>{strongEvidenceRefCount}</strong> / 2
        </small>
      </div>

      <div className="button-row">
        <button onClick={() => void submitRole()} disabled={submittingRole || runningCompile}>
          {submittingRole ? "Submitting..." : "Submit Role Input"}
        </button>
      </div>

      <hr />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 }}>
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
          <label>Reasoning:</label>
          <select value={reasoningLevel} onChange={(e) => setReasoningLevel(e.target.value)}>
            <option value="R2">R2</option>
            <option value="R3">R3</option>
            <option value="R4">R4</option>
            <option value="R5">R5</option>
          </select>
        </div>
        <div>
          <label>Policy:</label>
          <select value={policyLevel} onChange={(e) => setPolicyLevel(e.target.value)}>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
            <option value="P3">P3</option>
            <option value="P4">P4</option>
            <option value="P5">P5</option>
          </select>
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label>Governance Modes:</label>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {["FIRST-PRINCIPLES MODE", "DEVIL'S ADVOCATE MODE", "CONSTRAINTS-FIRST MODE", "/deepresearch"].map((mode) => (
            <label key={mode} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 400, color: "#334155" }}>
              <input
                type="checkbox"
                checked={governanceModes.includes(mode)}
                onChange={() => toggleGovernanceMode(mode)}
              /> {mode}
            </label>
          ))}
        </div>
        <small>Passed as structured governance_modes[] controls into deterministic compile.</small>
      </div>

      <div className="button-row">
        <button className="btn-primary" onClick={() => void runCompile()} disabled={runningCompile || submittingRole}>
          {runningCompile ? "Compiling..." : "Run Governed Compile"}
        </button>
      </div>

      {status && <div className="status">{status}</div>}
    </div>
  );
}
