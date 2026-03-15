import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import PolicySemanticsPanel from "./PolicySemanticsPanel";
import type { PolicyPackSemantics, RecommendationSemantics, ReviewState } from "../api";

function buildProps() {
  const pack: PolicyPackSemantics = {
    pack_id: "EU-AIA-v1",
    version: "v1",
    summary: { total_controls: 1, pass_count: 1, fail_count: 0 },
    controls: [
      {
        control_id: "EU-AIA-ART15-ACCURACY-ROBUSTNESS",
        status: "PASS",
        assessment_mode: "evidence_backed_assessment",
        assurance_level: "evidence_backed",
        compliance_position: "evidence_indicates_alignment",
        legal_confirmation_required: true,
        evidence_ids: ["evidence-123"],
        residual_uncertainty: "Legal confirmation pending independent counsel review.",
      },
    ],
  };
  const recommendation: RecommendationSemantics = {
    selected_vendor: "Fortinet",
    policy_pack_compliance: [pack],
  };
  const reviewState: ReviewState = {
    human_review_required: true,
    human_review_completed: true,
    reviewed_by: "reviewer-1",
    approved_by: "approver-1",
    open_exceptions: ["exception-a"],
    waived_controls: ["control-waiver-a"],
  };
  return { recommendation, pack, reviewState };
}

describe("PolicySemanticsPanel", () => {
  it("frontend rendering test for assessment_mode / assurance_level / compliance_position", () => {
    const { recommendation, pack, reviewState } = buildProps();
    render(
      <PolicySemanticsPanel
        recommendation={recommendation}
        policyPackCompliance={[pack]}
        reviewState={reviewState}
      />,
    );

    expect(screen.getByText(/Assessment Mode:/i)).toHaveTextContent("evidence_backed_assessment");
    expect(screen.getByText(/Assurance Level:/i)).toHaveTextContent("evidence_backed");
    expect(screen.getByText(/Compliance Position:/i)).toHaveTextContent("evidence_indicates_alignment");
  });

  it("test_ui_displays_legal_confirmation_required_and_residual_uncertainty", () => {
    const { recommendation, pack, reviewState } = buildProps();
    render(
      <PolicySemanticsPanel
        recommendation={recommendation}
        policyPackCompliance={[pack]}
        reviewState={reviewState}
      />,
    );

    const legalRows = screen.getAllByText(/Legal Confirmation Required:/i);
    const uncertaintyRows = screen.getAllByText(/Residual Uncertainty:/i);
    expect(legalRows[0]).toHaveTextContent("Yes");
    expect(uncertaintyRows[0]).toHaveTextContent(
      "Legal confirmation pending independent counsel review.",
    );
  });
});
