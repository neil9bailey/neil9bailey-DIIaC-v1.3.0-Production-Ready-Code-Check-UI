# IMPLEMENTATION_CLOSURE_MATRIX

Generated_at_utc: 2026-03-13T01:05:00Z
Repository_root: F:/code/diiac/diiac_v1.3.0_ui
Commit: bfe6ea2
Scope: Wave 1 blockers only (R1-R6)
Assessment_mode: strict (code + direct tests required)

## Ticket Matrix

| epic_id | ticket_id | status | exact files changed | exact symbols/endpoints/schemas affected | exact tests covering change | exact verification commands used | remaining gaps | enforcement-incomplete note | docs-vs-runtime contradiction note |
|---|---|---|---|---|---|---|---|---|---|
| E6 | R1 | implemented | app.py; tests/test_admin_console.py | `app.py:_replay_validation_error`; `app.py:_validate_replay_payload`; `app.py:verify_replay` (`/verify/replay`) | `test_replay_does_not_inject_legacy_non_negotiables`; `test_replay_does_not_inject_legacy_risk_flags`; `test_replay_rejects_missing_evidence_ids_without_auto_refs`; `test_replay_fails_with_structured_error_on_missing_required_provenance`; `test_replay_verification_certificate_for_deterministic_execution` | `python -m pytest -q --basetemp .pytest_tmp`; `rg -n "llm-hallucination-risk|auto-ref-|MISSING_REPLAY_INPUTS|MISSING_REQUIRED_PROVENANCE|MISSING_EVIDENCE_IDS" app.py` | None in R1 scope | No (production replay path now hard-fails missing provenance/evidence; no legacy injected defaults) | No contradiction found for R1 targets |
| E1 | R2 | implemented | backend-ui-bridge/server.js; app.py; Frontend/src/api.ts; tests/test_admin_console.py | `backend-ui-bridge/server.js:loadBridgeTrustState`; `BRIDGE_TRUST_BLOCKED` startup error; `/health` trust block state; `/readiness` trust check; `/admin/config/effective` signing trust fields; `app.py:/admin/health` + `/health` trust blocker exposure; `Frontend/src/api.ts:EffectiveConfigResponse.signing` | `test_bridge_non_dev_requires_registered_active_key`; `test_bridge_non_dev_rejects_mismatched_registered_key`; `test_bridge_runtime_trust_parity_contract`; `test_bridge_and_runtime_fail_same_trust_misconfiguration_e2e`; existing runtime tests `test_non_dev_runtime_blocks_ephemeral_signing`; `test_non_dev_runtime_requires_registered_active_signing_key` | `python -m pytest -q --basetemp .pytest_tmp`; `node --check backend-ui-bridge/server.js`; `rg -n "loadBridgeTrustState|BRIDGE_TRUST_BLOCKED|signing_trust_blockers|production_trust_ready" backend-ui-bridge/server.js` | Production `/admin/config/effective` parity cannot be queried without Entra auth mode; startup parity still fully enforced in non-dev via tests | No for non-dev trust parity enforcement | No contradiction found for R2 targets |
| E3 | R3 | implemented | app.py; tests/test_admin_console.py | `app.py:_build_human_readable_sections` (removed synthesized Executive Summary/Risk Register defaults); `app.py:_enforce_sections`; `BOARD_SECTION_INCOMPLETE` hard gate | `test_missing_risk_register_fails_board_section_incomplete`; `test_missing_executive_summary_fails_board_section_incomplete`; `test_production_output_contains_no_placeholder_sections` | `python -m pytest -q --basetemp .pytest_tmp`; `rg -n "BOARD_SECTION_INCOMPLETE|_enforce_sections|Risk Register|Executive Summary" app.py` | None in R3 scope | No (production path now fails on missing required sections instead of synthesizing placeholder content) | No contradiction found for R3 targets |
| E3 | R4 | implemented | app.py; openapi.yaml; Frontend/src/api.ts; Frontend/src/MultiRoleGovernedCompilePanel.tsx; tests/test_admin_console.py | `app.py:_validate_compile_payload` (`success_metrics` required fields); `app.py:_validate_success_metric_kpi`; `INVALID_SUCCESS_METRICS` gate; `openapi.yaml:SuccessMetricInput`; `Frontend/src/api.ts` success metric contract; `MultiRoleGovernedCompilePanel.tsx` KPI parsing/validation + payload emission | `test_success_metrics_require_baseline_target_unit_window_owner`; `test_principle_only_metric_fails_invalid_success_metrics`; `test_kpi_schema_round_trip_contract` | `python -m pytest -q --basetemp .pytest_tmp`; `npm --prefix Frontend run build`; `rg -n "success_metrics|SuccessMetricInput|INVALID_SUCCESS_METRICS" app.py openapi.yaml Frontend/src/api.ts Frontend/src/MultiRoleGovernedCompilePanel.tsx` | None in R4 scope | No (invalid KPI schemas now block compile) | No contradiction found for R4 targets |
| E5 | R5 | implemented | app.py; contracts/vendors/canonical_vendors.json; tests/test_admin_console.py | `app.py:_load_vendor_registry` (`evidence_policy` thresholds/classes); class-aware freshness evaluation in compile path; `STALE_CRITICAL_EVIDENCE` hard gate for high assurance; noncritical stale warning path; `contracts/vendors/canonical_vendors.json:evidence_policy` | `test_stale_security_evidence_blocks_high_assurance`; `test_stale_pricing_evidence_blocks_high_assurance`; `test_noncritical_stale_evidence_warns_without_false_pass` | `python -m pytest -q --basetemp .pytest_tmp`; `rg -n "STALE_CRITICAL_EVIDENCE|stale_noncritical|freshness_threshold_days|critical_classes" app.py contracts/vendors/canonical_vendors.json` | None in R5 scope | No (critical stale evidence now blocks high-assurance compile) | No contradiction found for R5 targets |
| E2 | R6 | implemented | app.py; contracts/vendors/canonical_vendors.json; tests/test_admin_console.py | Vendor mismatch enforcement in compile path: `selected_vendor_misaligned_claims`; `general_scope_primary_claims`; `competitor_primary_claims`; hard gates `VENDOR_EVIDENCE_MISMATCH` and `COMPETITOR_PRIMARY_EVIDENCE`; tightened first-party + independent support requirement | `test_selected_vendor_rejects_competitor_primary_evidence`; `test_vendor_scope_general_does_not_satisfy_first_party_requirement`; `test_vendor_evidence_mismatch_hard_fails_selected_vendor` | `python -m pytest -q --basetemp .pytest_tmp`; `rg -n "VENDOR_EVIDENCE_MISMATCH|COMPETITOR_PRIMARY_EVIDENCE|vendor_scope=general" app.py` | None in R6 scope | No (selected-vendor mismatch and competitor-primary evidence both hard-fail) | No contradiction found for R6 targets |

## Overall Verdict By Epic (1-8)

| epic | verdict |
|---|---|
| Epic 1 | Partially implemented (R2 complete in this run; other Epic 1 items out of scope) |
| Epic 2 | Partially implemented (R6 complete in this run; other Epic 2 items out of scope) |
| Epic 3 | Partially implemented (R3/R4 complete in this run; remaining Epic 3 items out of scope) |
| Epic 4 | Not implemented in this run (explicitly out of scope) |
| Epic 5 | Partially implemented (R5 complete in this run; remaining Epic 5 items out of scope) |
| Epic 6 | Partially implemented (R1 complete in this run; remaining Epic 6 items out of scope) |
| Epic 7 | Not implemented in this run (explicitly out of scope) |
| Epic 8 | Not implemented in this run (explicitly out of scope) |

## Top 10 Remaining Blockers (Post R1-R6)

1. Policy semantics uplift (Epic 4) still lacks full response contract + UI rendering.
2. Golden artifact fixture suite (Epic 7) is still missing.
3. Negative fixture matrix for every hard gate (Epic 7) is still incomplete.
4. Human review workflow/ledger event chain (Epic 8) is still missing.
5. Response-side OpenAPI schemas still under-specify backend semantics in several endpoints.
6. UI exposure for assurance/compliance semantics remains incomplete.
7. Production Entra-authenticated bridge parity endpoint test path is not covered (startup parity is covered).
8. Additional trust key-rotation verification tests remain out of scope for this run.
9. Sensitivity/scoring analysis and richer board rendering are not part of this wave.
10. Operational runbooks/package hardening for verifier materials are not implemented in this run.

## Exact Next Actions

1. Implement Epic 4 response-side semantics model and UI rendering.
2. Add golden fixtures and CI snapshot drift controls (Epic 7).
3. Add full negative fixture coverage for all hard quality gates (Epic 7).
4. Implement review/approval event logging and approval accountability workflow (Epic 8).
5. Expand OpenAPI response schemas to match runtime semantics.

## Files/Symbols Most Likely Needing Further Work

- app.py: policy semantics response assembly around decision summary/control outputs.
- openapi.yaml: response schemas for semantics/trust/readiness.
- Frontend/src/*: policy/assurance semantics presentation components.
- tests/: golden + negative fixture suites for expanded CI gating.
- backend-ui-bridge/server.js: authenticated production parity endpoint contract tests.
