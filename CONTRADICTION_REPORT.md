# CONTRADICTION_REPORT

Generated_at_utc: 2026-03-13T00:00:30Z
Commit: 612e654

## Detected Contradictions

1. Intent preservation claim vs replay implementation.
- claimed_resolved: bridge/runtime no longer overwrite constraints with generic defaults.
- contradictory_code: `app.py` `/verify/replay` still injects `deterministic-governance`, `llm-hallucination-risk`, and `auto-ref-*`.
- contradiction_type: old behavior still present.

2. Trust parity claim vs bridge trust enforcement depth.
- claimed_resolved: bridge and runtime follow identical trust rules.
- contradictory_code: `backend-ui-bridge/server.js` startup does not enforce public key registry registration/match the way `app.py` does.
- contradiction_type: implementation mismatch.

3. Policy semantics uplift claim vs frontend exposure.
- claimed_resolved: semantics uplift is backend/frontend aligned.
- contradictory_code: no frontend component references for rendering `assessment_mode`, `assurance_level`, `compliance_position`, `legal_confirmation_required`, `residual_uncertainty`.
- contradiction_type: UI contract gap.

4. Contract uplift claim vs OpenAPI response model.
- claimed_resolved: contract updated end-to-end.
- contradictory_code: `openapi.yaml` includes request-side review fields but no full response-side policy semantics/trust schema.
- contradiction_type: API schema gap.

5. Freshness gate claim vs runtime enforcement.
- claimed_resolved: evidence freshness controls are gating quality.
- contradictory_code: stale evidence is warning-only in quality failures, not a hard gate code.
- contradiction_type: control posture weaker than claimed.

6. Board completeness hard-fail claim vs test proof depth.
- claimed_resolved: incomplete sections hard-fail reliably.
- contradictory_tests: no direct test asserting `BOARD_SECTION_INCOMPLETE` on missing required section.
- contradiction_type: tests do not fully prove claim.

7. Human accountability claim vs ledger audit chain.
- claimed_resolved: high-assurance outputs include explicit accountable review chain.
- contradictory_code: no dedicated review/approval event append path in trust ledger.
- contradiction_type: auditability gap.

8. Verification hardening claim vs fixture coverage.
- claimed_resolved: golden and negative artifact-quality suites in place.
- contradictory_repo_state: `tests/golden` and `tests/negative` are absent.
- contradiction_type: missing validation assets.

9. CI trust gating claim vs workflow specificity.
- claimed_resolved: CI has trust-mode and sign/verify gates.
- contradictory_workflow: no explicit trust-mode matrix and no dedicated mandatory offline verifier gate job.
- contradiction_type: CI-time enforcement incomplete.

10. Vendor alignment claim vs test evidence.
- claimed_resolved: competitor primary evidence rejection fully validated.
- contradictory_tests: no direct negative test proving `COMPETITOR_PRIMARY_EVIDENCE` gate trigger.
- contradiction_type: test evidence insufficiency.
