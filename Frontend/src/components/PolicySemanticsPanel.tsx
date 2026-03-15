import type { PolicyPackSemantics, RecommendationSemantics, ReviewApprovalEvent, ReviewState } from "../api";

interface Props {
  recommendation?: RecommendationSemantics;
  policyPackCompliance?: PolicyPackSemantics[];
  reviewState?: ReviewState;
  reviewEvents?: ReviewApprovalEvent[];
}

function yesNo(value: boolean | undefined): string {
  return value ? "Yes" : "No";
}

export default function PolicySemanticsPanel({
  recommendation,
  policyPackCompliance,
  reviewState,
  reviewEvents,
}: Props) {
  const packs = policyPackCompliance || recommendation?.policy_pack_compliance || [];
  if (!packs.length && !reviewState && !reviewEvents?.length) return null;

  return (
    <div className="panel" data-testid="policy-semantics-panel">
      <h3>Policy Semantics and Review Accountability</h3>
      {packs.map((pack, packIdx) => (
        <div key={`${pack.pack_id || "pack"}-${packIdx}`} style={{ marginBottom: 12 }}>
          <h4 style={{ marginBottom: 4 }}>
            {pack.pack_id || "Policy Pack"} {pack.version ? `(${pack.version})` : ""}
          </h4>
          <div className="muted-text" style={{ marginBottom: 6 }}>
            Controls: {pack.summary?.total_controls ?? pack.controls.length} | PASS: {pack.summary?.pass_count ?? 0} | FAIL: {pack.summary?.fail_count ?? 0}
          </div>
          {(pack.controls || []).map((control) => (
            <div key={`${control.control_id}`} className="console-box" style={{ marginBottom: 8 }}>
              <div><strong>{control.control_id}</strong></div>
              <div>Status: {control.status} | Assessment Mode: {control.assessment_mode}</div>
              <div>Assurance Level: {control.assurance_level} | Compliance Position: {control.compliance_position}</div>
              <div>Legal Confirmation Required: {yesNo(control.legal_confirmation_required)}</div>
              <div>Residual Uncertainty: {control.residual_uncertainty}</div>
              <div>Evidence IDs: {(control.evidence_ids || []).join(", ") || "None"}</div>
            </div>
          ))}
        </div>
      ))}

      {reviewState && (
        <div className="console-box" style={{ marginBottom: 8 }}>
          <h4>Review State</h4>
          <div>Human Review Required: {yesNo(reviewState.human_review_required)}</div>
          <div>Human Review Completed: {yesNo(reviewState.human_review_completed)}</div>
          <div>Reviewed By: {reviewState.reviewed_by || "Not set"}</div>
          <div>Approved By: {reviewState.approved_by || "Not set"}</div>
          <div>Open Exceptions: {(reviewState.open_exceptions || []).join(", ") || "None"}</div>
          <div>Waived Controls: {(reviewState.waived_controls || []).join(", ") || "None"}</div>
        </div>
      )}

      {reviewEvents && reviewEvents.length > 0 && (
        <div className="console-box">
          <h4>Review Ledger Events</h4>
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {reviewEvents.map((event, idx) => (
              <li key={`${event.event_ref_id || idx}`}>
                {event.event_type || "REVIEW_EVENT"} | ref={event.event_ref_id || "n/a"} | record={event.record_id ?? "n/a"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
