# BEHAVIORAL_DELTA_REPORT

Generated_at_utc: 2026-03-15T12:44:00Z  
Commit: 28ca865

## Trust Separation (R2, R10)

- previous_behavior: bridge/runtime could diverge on non-dev trust checks.
- current_behavior: bridge and runtime enforce registered active key + key-match blocking in non-dev; trust bundles include lifecycle metadata.
- exact_code_refs: `app.py` startup trust guards; `backend-ui-bridge/server.js:loadBridgeTrustState`; `scripts/verify_decision_pack.js:validateKeyValidityWindow`.
- exact_tests: `test_bridge_non_dev_requires_registered_active_key`; `test_bridge_non_dev_rejects_mismatched_registered_key`; `test_bridge_runtime_parity_for_non_dev_trust_blockers`; `test_trust_bundle_contains_validity_window`.
- change_status: complete.
- remaining_for_decision_grade: live non-dev deployment verification.

## Replay/Input Default Injection (R1)

- previous_behavior: replay/default paths could synthesize fallback constraints/provenance.
- current_behavior: replay rejects missing required provenance/evidence with structured errors; no deterministic-governance, llm-hallucination-risk, or auto-ref synthesis on production replay path.
- exact_code_refs: `app.py:_validate_replay_payload`; `app.py:verify_replay`.
- exact_tests: `test_replay_does_not_inject_legacy_non_negotiables`; `test_replay_does_not_inject_legacy_risk_flags`; `test_replay_rejects_missing_evidence_ids_without_auto_refs`; `test_replay_fails_with_structured_error_on_missing_required_provenance`.
- change_status: complete.
- remaining_for_decision_grade: none in local runtime path.

## Board Completeness + KPI Strictness (R3, R4)

- previous_behavior: structurally valid reports could pass with placeholders/non-measurable KPI intent.
- current_behavior: missing required sections hard-fail; KPI schema requires metric_name/baseline/target/unit/window/owner and rejects principle-only values.
- exact_code_refs: `app.py:_enforce_sections`; `app.py:_validate_success_metric_kpi`; `openapi.yaml:SuccessMetricInput`.
- exact_tests: `test_missing_risk_register_fails_board_section_incomplete`; `test_missing_executive_summary_fails_board_section_incomplete`; `test_production_output_contains_no_placeholder_sections`; `test_success_metrics_require_baseline_target_unit_window_owner`; `test_principle_only_metric_fails_invalid_success_metrics`; `test_kpi_schema_round_trip_contract`.
- change_status: complete.
- remaining_for_decision_grade: none in local runtime path.

## Evidence/Vendor Hardening (R5, R6, R14)

- previous_behavior: stale critical evidence and vendor mismatch could under-block in edge cases.
- current_behavior: class-aware stale critical evidence blocks high-assurance; competitor-primary and selected-vendor mismatch are hard-failed; selected-vendor dossier completeness + product normalization required.
- exact_code_refs: `app.py` vendor/evidence hard-gate block; `contracts/vendors/canonical_vendors.json`.
- exact_tests: `test_stale_security_evidence_blocks_high_assurance`; `test_stale_pricing_evidence_blocks_high_assurance`; `test_selected_vendor_rejects_competitor_primary_evidence`; `test_vendor_scope_general_does_not_satisfy_first_party_requirement`; `test_vendor_evidence_mismatch_hard_fails_selected_vendor`; `test_selected_vendor_requires_security_pricing_operational_support`; `test_product_label_normalization_is_applied`; `test_incomplete_selected_vendor_dossier_fails`.
- change_status: complete.
- remaining_for_decision_grade: ongoing registry curation operations outside code path.

## Policy Semantics + UI Contract (R7)

- previous_behavior: policy interpretation could be PASS-centric in API/UI surfaces.
- current_behavior: API schema/runtime/frontend expose and render assessment_mode, assurance_level, compliance_position, legal_confirmation_required, evidence_ids, residual_uncertainty.
- exact_code_refs: `openapi.yaml:PolicyControlResult`; `Frontend/src/api.ts`; `Frontend/src/components/PolicySemanticsPanel.tsx`; `app.py` policy control construction.
- exact_tests: `test_api_schema_contract_for_policy_semantics_response`; `frontend rendering test for assessment_mode / assurance_level / compliance_position`; `test_ui_displays_legal_confirmation_required_and_residual_uncertainty`.
- change_status: complete.
- remaining_for_decision_grade: none in local contract path.

## Provider Invariance + Parity (R8, R9)

- previous_behavior: provider labels had potential to leak into recommendation narrative; bridge/runtime parity not explicitly regression-tested.
- current_behavior: provider metadata excluded from recommendation basis; recommendation invariant under provider-label-only changes; bridge/runtime parity suite covers trust, intent, review/policy semantics.
- exact_code_refs: `app.py:_build_execution`; `tests/test_wave2_parity_contracts.py`.
- exact_tests: `test_provider_metadata_does_not_leak_into_recommendation`; `test_recommendation_invariant_under_provider_label_change`; `test_decision_basis_references_vendor_not_provider`; `test_bridge_runtime_parity_for_non_dev_trust_blockers`; `test_bridge_runtime_parity_for_intent_preservation`; `test_bridge_runtime_parity_for_review_state_and_policy_semantics`.
- change_status: complete.
- remaining_for_decision_grade: live deployment parity smoke.

## Golden/Negative Fixture Architecture (R11, R12)

- previous_behavior: coverage focused on general suite with limited fixture-level decision-pack lock-in.
- current_behavior: deterministic golden fixtures for enterprise/transport/finance and one negative fixture per required hard gate.
- exact_code_refs: `tests/golden/*.json`; `tests/test_golden_exports.py`; `tests/negative/*.json`; `tests/test_negative_fixtures.py`.
- exact_tests: `test_golden_it_enterprise_export`; `test_golden_transport_export`; `test_golden_finance_export`; `test_negative_fixture_cases[...]` (15 scenarios).
- change_status: complete.
- remaining_for_decision-grade: fixture governance process maintenance.

## Human Accountability Ledger (R13)

- previous_behavior: review/approval semantics existed without full immutable event surfacing guarantees.
- current_behavior: review completion, approval, exceptions, waivers append ledger-linked events and surface in exports/UI.
- exact_code_refs: `app.py:_build_review_event_refs`; `openapi.yaml:ReviewState`; `openapi.yaml:ReviewApprovalEvent`; `Frontend/src/components/PolicySemanticsPanel.tsx`.
- exact_tests: `test_review_completion_appends_ledger_event`; `test_approval_appends_ledger_event`; `test_exceptions_and_waivers_surface_in_export_and_ui`.
- change_status: complete.
- remaining_for_audit-grade: operational retention/rotation controls in deployed environment.
