export default function GovernanceNotice() {
  return (
    <div className="governance-notice">
      <strong>Governance Notice</strong>
      <p style={{ margin: "4px 0 0", color: "#334155", fontSize: 12 }}>
        AI-assisted output is treated as <strong>untrusted input</strong> until DIIaC governance checks pass.
        Decisions are policy-bound, deterministically compiled, cryptographically signed, and recorded in an immutable audit ledger.
      </p>
      <p style={{ margin: "6px 0 0", color: "#475569", fontSize: 12 }}>
        If evidence quality or policy controls fail, recommendation approval is automatically blocked.
      </p>
    </div>
  );
}
