export default function GovernanceNotice() {
  return (
    <div className="governance-notice">
      <strong>Governance Notice</strong>
      <p style={{ margin: "4px 0 0", color: "#334155", fontSize: 12 }}>
        AI-assisted content is treated as <strong>untrusted input</strong>.
        All outputs are deterministically governed, policy-bound,
        and recorded in an immutable audit ledger.
      </p>
    </div>
  );
}
