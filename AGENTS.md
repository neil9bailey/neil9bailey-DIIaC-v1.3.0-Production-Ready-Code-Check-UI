# DIIaC Codex Execution Contract

## Mission
Harden and complete DIIaC without weakening:
- governance
- deterministic outputs
- evidence integrity
- replayability
- signature verification
- trust separation
- auditability
- human oversight
- LLM-style intent capture

The core architecture must remain intact:
- human intent in
- governed compilation
- deterministic scoring/transformation
- evidence-bound outputs
- signed export artifacts
- replayable audit trail
- policy-pack enforcement
- Merkle/integrity verification

## Source of truth
Before making changes, read:
- IMPLEMENTATION_CLOSURE_MATRIX.md
- QUALITY_GATES_REPORT.json
- CONTRADICTION_REPORT.md
- UNRESOLVED_GAPS.md
- VERIFICATION_MANIFEST.json
- VALIDATION_OUTPUTS.md

Treat those files as the authoritative list of remaining gaps and contradictions.

## Operating rules
- Do not create new branches.
- Work only in the current repository.
- Prefer targeted edits over broad refactors.
- Do not claim completion unless code, tests, and regenerated closure artifacts all support the claim.
- Do not rely on docs-only completion claims.
- Do not mask missing behavior with placeholders or synthetic defaults.
- Do not silently auto-heal trust in non-dev.
- Do not weaken existing hard gates.
- Do not emit narrative “done” summaries without machine-checkable evidence.

## Non-negotiables
- No placeholder-based fixes.
- No self-asserting trust in non-dev.
- No competitor-primary evidence satisfying selected-vendor requirements.
- No stale critical evidence passing high-assurance outputs.
- No provider metadata leaking into vendor recommendation fields.
- No incomplete board sections on production paths.
- No high-assurance output without explicit review/accountability state.

## Required outputs after each task
Regenerate:
- IMPLEMENTATION_CLOSURE_MATRIX.md
- VERIFICATION_MANIFEST.json
- QUALITY_GATES_REPORT.json
- UNRESOLVED_GAPS.md
- CONTRADICTION_REPORT.md
- VALIDATION_OUTPUTS.md

## Completion rule
A task is complete only if:
- the requested tickets are implemented,
- tests proving them are added and passing,
- the regenerated closure pack marks those tickets implemented,
- the contradiction report no longer lists the targeted gaps,
- the worktree is clean after commit.

## Verification commands
Always run, unless a task explicitly states a smaller scoped subset first:
- git rev-parse --short HEAD
- python -m pytest -q --basetemp .pytest_tmp
- node --check backend-ui-bridge/server.js
- npm --prefix Frontend run build
- python scripts_e2e_runtime_smoke.py
- python scripts_e2e_assurance_validation.py
- python scripts_production_readiness_check.py
- node scripts/verify_decision_pack.js <generated_artifact_dir> contracts/keys/public_keys.json

If new suites are added, run them too.

## Failure handling
If a requested item cannot be completed:
- stop claiming completion,
- document the blocker precisely,
- identify exact files/symbols involved,
- state whether the blocker is code, test, contract, or environment related.

## Response format
At the end of each task, output only:
1. tickets completed
2. exact files changed
3. exact tests added/updated
4. commands run + pass/fail
5. regenerated artifact list
6. remaining blockers, if any# BEHAVIORAL_DELTA_REPORT

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
