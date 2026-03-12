# BEHAVIORAL_DELTA_REPORT

Generated_at_utc: 2026-03-13T00:00:20Z
Commit: 612e654

## Trust Registry Mutation

- previous_behavior: trust registry reconciliation/mutation could occur without strict production separation.
- current_behavior: non-dev auto-registration disabled; dev auto-registration requires explicit `TRUST_REGISTRY_DEV_AUTOREGISTER=true`.
- exact_code_refs: `app.py` create_app trust registry write block; non-dev startup checks.
- exact_tests: `test_runtime_reconciles_public_key_registry_entry`; `test_non_dev_runtime_requires_registered_active_signing_key`.
- change_status: partial.
- remaining_for_decision_grade: structured startup error taxonomy + bridge/runtime trust parity checks.

## Non-Dev Ephemeral Signing

- previous_behavior: ephemeral path existed in key loader.
- current_behavior: non-dev blocks ephemeral key use in runtime and bridge startup.
- exact_code_refs: `app.py` key mode checks; `backend-ui-bridge/server.js` `loadSigningKeyPair`.
- exact_tests: `test_non_dev_runtime_blocks_ephemeral_signing`.
- change_status: partial.
- remaining_for_audit_grade: bridge registry key-match enforcement and explicit bridge non-dev negative coverage.

## Sign-Then-Verify Export Gate

- previous_behavior: signed artifacts existed, but export release gating was weaker.
- current_behavior: export routes verify signature before publication; compile aborts if immediate verify fails.
- exact_code_refs: `app.py` `_verify_signature_contract`, `_generate_signed_export_artifacts`, `/decision-pack/*/export*`.
- exact_tests: `test_signed_export_includes_verification_metadata_and_schema_version`.
- change_status: partial.
- remaining_for_audit_grade: explicit tampered signature and unknown key-id negative tests.

## Claim/Evidence Compile Gate

- previous_behavior: weaker claim-to-evidence closure.
- current_behavior: unresolved evidence triggers compile hard-fail.
- exact_code_refs: `app.py` `UNRESOLVED_EVIDENCE` hard gate.
- exact_tests: `test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics`.
- change_status: partial.
- remaining_for_decision_grade: broaden gate tests across placeholder and competitor-primary cases.

## Board Completeness Gate

- previous_behavior: placeholder/structural completion could pass with weak substance.
- current_behavior: board completeness hard gate (`BOARD_SECTION_INCOMPLETE`) exists.
- exact_code_refs: `app.py` `_enforce_sections` + hard gate block.
- exact_tests: indirect section-presence checks only.
- change_status: partial.
- remaining_for_decision_grade: explicit missing-section and placeholder-section negative tests.

## KPI Measurability

- previous_behavior: principle-only metrics could pass.
- current_behavior: measurable KPI gate exists (`INVALID_SUCCESS_METRICS`).
- exact_code_refs: `app.py` `_is_measurable_metric`, `_metric_to_kpi`, hard gate block.
- exact_tests: `test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics`.
- change_status: partial.
- remaining_for_audit_grade: strict KPI schema validation for baseline/target/timeframe/tolerance.

## Intent Preservation

- previous_behavior: bridge default values could overwrite intent.
- current_behavior: bridge compile path forwards user constraints; default overwrite removed in that path.
- exact_code_refs: `backend-ui-bridge/server.js` `/api/llm-governed-compile` payload mapping.
- exact_tests: `test_inline_payload_preserves_intent_without_default_overwrite`.
- change_status: partial.
- remaining_for_decision_grade: remove replay fallback default injection and add missing-input markers.

## Policy Semantics Uplift

- previous_behavior: PASS-centric semantics could overstate assurance.
- current_behavior: runtime emits `assessment_mode`, `assurance_level`, `compliance_position`, `legal_confirmation_required`, `evidence_ids`, `residual_uncertainty`.
- exact_code_refs: `app.py` policy control result construction.
- exact_tests: no direct enum assertion suite.
- change_status: partial.
- remaining_for_audit_grade: full enum lifecycle + frontend rendering + OpenAPI response schema coverage.

## Vendor Normalization/Freshness

- previous_behavior: weaker canonical vendor and freshness posture.
- current_behavior: canonical vendor registry and mismatch checks added; freshness status computed.
- exact_code_refs: `contracts/vendors/canonical_vendors.json`; `app.py` vendor/freshness blocks.
- exact_tests: vendor name preservation + LLM freshness override tests.
- change_status: partial.
- remaining_for_decision_grade: hard-fail stale critical evidence + class-complete dossier checks.

## Human Review Gate

- previous_behavior: high-assurance posture could be inferred without strict review metadata gate.
- current_behavior: high-assurance compile blocked without complete review state.
- exact_code_refs: `app.py` `REVIEW_STATE_INCOMPLETE` gate block.
- exact_tests: `test_high_assurance_requires_completed_review_state`.
- change_status: partial.
- remaining_for_audit_grade: immutable approval events in ledger + board/UI exception/waiver rendering.
