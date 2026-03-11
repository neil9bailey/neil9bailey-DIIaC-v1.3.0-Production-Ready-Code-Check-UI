import { useEffect, useMemo, useState } from "react";
import { type BusinessProfileEntry, listBusinessProfiles, runGovernedCompile, submitRoleInput } from "./api";

interface Props {
  role: string;
  onExecutionComplete: (executionId: string) => void;
}

export default function MultiRoleGovernedCompilePanel({ role, onExecutionComplete }: Props) {
  const [executionContextId, setExecutionContextId] = useState("ctx-ui");
  const [selectedRole, setSelectedRole] = useState("ACTING_CTO");
  const [domain, setDomain] = useState("enterprise-solution");
  const [assertion, setAssertion] = useState("API-first architecture");
  const [businessProfile, setBusinessProfile] = useState("transport_profile_v1");
  const [profiles, setProfiles] = useState<BusinessProfileEntry[]>([]);
  const [schemaId, setSchemaId] = useState("GENERAL_SOLUTION_BOARD_REPORT_V1");
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

  async function submitRole() {
    try {
      setStatus("Submitting role input...");
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
      setStatus("Running governed compile...");
      const res = await runGovernedCompile({
        execution_context_id: executionContextId,
        schema_id: effectiveSchemaId,
        profile_id: businessProfile,
        reasoning_level: "R4",
        policy_level: "P4",
      });
      const executionId = res.execution_id || res.execution_state?.execution_id;
      if (executionId) {
        onExecutionComplete(executionId);
        setStatus(`Governed compile complete: ${executionId}`);
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
      <h2>Multi-Role Governed Compile (New)</h2>

      <div>
        <label>Execution Context ID:</label>
        <input value={executionContextId} onChange={(e) => setExecutionContextId(e.target.value)} />
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
        <label>Domain:</label>
        <input value={domain} onChange={(e) => setDomain(e.target.value)} />
      </div>

      <div>
        <label>Assertion:</label>
        <input value={assertion} onChange={(e) => setAssertion(e.target.value)} />
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

      <button onClick={() => void runCompile()}>Run Governed Compile</button>

      {status && <div className="status">{status}</div>}
    </div>
  );
}
