# IMPLEMENTATION_CLOSURE_MATRIX

Generated_at_utc: 2026-03-12T23:59:00Z
Repository_root: F:/code/diiac/diiac_v1.3.0_ui
Commit: 612e654
Assessment_mode: strict_evidence_backed

## Ticket Matrix

| ticket_id | status | files_changed | symbols/endpoints/schemas affected | tests covering change | verification commands used | remaining gaps | enforcement/docs contradiction note |
|---|---|---|---|---|---|---|---|
| E1-T01 | partial | app.py; tests/test_admin_console.py | create_app trust-registry block; allow_registry_autoregister; non-dev key checks | test_runtime_reconciles_public_key_registry_entry; test_non_dev_runtime_requires_registered_active_signing_key | CMD-02, CMD-10 | startup failures are RuntimeError not structured error_code; dev opt-in mutation remains | docs expect deterministic startup taxonomy; runtime uses exceptions |
| E1-T02 | partial | app.py; backend-ui-bridge/server.js; Frontend/src/api.ts | signing_mode fields; loadSigningKeyPair; /health;/admin/health;/admin/config/effective | test_non_dev_runtime_blocks_ephemeral_signing | CMD-02, CMD-03, CMD-10, CMD-11 | bridge does not enforce registry key-match parity with runtime; no parity contract test | docs claim identical rules but bridge trust checks are shallower |
| E1-T03 | partial | app.py; scripts/verify_decision_pack.js; tests/test_admin_console.py | _verify_signature_contract; _generate_signed_export_artifacts; /decision-pack/*/export | test_signed_export_includes_verification_metadata_and_schema_version; test_verify_pack_detects_hash_and_manifest_tampering | CMD-02, CMD-08, CMD-09 | no direct negative for tampered signature on export route; no unknown-key export test | docs claim CI-grade sign/verify negatives; coverage is partial |
| E1-T04 | partial | app.py; scripts/verify_decision_pack.js | trust_bundle.json artifact; resolver uses trust bundle first | none direct | CMD-08, CMD-09 | no valid_from/valid_to fields; no key-rotation regression test | docs claim rotation-safe windows/tests; absent |
| E1-T05 | partial | app.py; backend-ui-bridge/server.js; openapi.yaml; Frontend/src/api.ts | /trust/status; /admin/health trust fields; EffectiveConfigResponse.signing | test_health_and_admin_health_include_readiness_checks | CMD-02, CMD-11, CMD-15 | OpenAPI/UI parity incomplete for trust fields and blocker rendering | docs expect contract/UI parity; partial |
| E2-T01 | partial | app.py; tests/test_admin_console.py | semantic_claim_seed; deterministic claim_id hash | test_deterministic_same_inputs_same_scores_and_structured_sections; test_evidence_trace_linking_and_required_artifacts_present | CMD-02, CMD-09 | no direct mutation/stability/collision tests | docs require explicit semantic-id tests |
| E2-T02 | partial | app.py; openapi.yaml; Frontend/src/api.ts | evidence object v2 fields in runtime build | test_evidence_trace_linking_and_required_artifacts_present | CMD-02, CMD-08 | no strict schema validator; no missing-captured_at fail test | docs claim required-field hard-fail behavior |
| E2-T03 | partial | app.py; tests/test_admin_console.py; scripts_e2e_runtime_smoke.py | UNRESOLVED_EVIDENCE gate; unresolved_claim_bindings | test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics | CMD-02, CMD-09 | no explicit placeholder-URN negative; no export-time rebinding check | docs ask explicit unresolved placeholder coverage |
| E2-T04 | partial | app.py; contracts/vendors/canonical_vendors.json; tests/test_admin_console.py | VENDOR_EVIDENCE_MISMATCH; COMPETITOR_PRIMARY_EVIDENCE; vendor_scope mapping | none direct | CMD-09, CMD-12 | competitor-domain direct negative tests missing; vendor_scope=general bypass risk | docs claim stronger enforced alignment with tests |
| E2-T05 | partial | app.py; Frontend/src/api.ts | provenance_class and independence_level assignment | none | CMD-08, CMD-13 | no UI rendering and no deterministic provenance tests | docs expect report/UI provenance visibility |
| E3-T01 | partial | app.py; tests/test_admin_console.py; scripts_e2e_runtime_smoke.py | _enforce_sections; BOARD_SECTION_INCOMPLETE gate | indirect section presence test only | CMD-02, CMD-09 | no direct missing-section negative test | docs claim hard-fail coverage depth not fully proven |
| E3-T02 | partial | contracts/business-profiles/*_profile_v1.json; app.py | required_sections expanded; required_report_fields checks | test_deterministic_same_inputs_same_scores_and_structured_sections | CMD-02, CMD-09 | no profile schema completeness test; no empty regulatory section negative | docs specify negative tests absent in suite |
| E3-T03 | partial | app.py; openapi.yaml; Frontend/src/MultiRoleGovernedCompilePanel.tsx | _metric_to_kpi; INVALID_SUCCESS_METRICS gate | test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics | CMD-02, CMD-09 | baseline/timeframe/tolerance not strictly validated | docs require strict KPI schema validation |
| E3-T04 | partial | app.py; backend-ui-bridge/server.js; tests/test_admin_console.py | intent_signals; MISSING_REGULATORY_CONSTRAINTS; MISSING_SUCCESS_TARGETS | test_inline_payload_preserves_intent_without_default_overwrite | CMD-02, CMD-12 | no pointer-level intent_coverage_map; no budget omission negative test | docs require source->target mapping not just signals |
| E3-T05 | partial | app.py; tests/test_admin_console.py | DECISION_PROVENANCE_INCONSISTENT gate; decision_basis | none direct | CMD-09, CMD-12 | only provider-token leakage checked; broader leakage not tested | docs claim broader provenance consistency |
| E4-T01 | partial | app.py; openapi.yaml | control semantics fields assessment_mode/assurance_level/compliance_position/legal_confirmation_required/evidence_ids/residual_uncertainty | none direct | CMD-09, CMD-13 | target enum coverage incomplete; no enum validation tests | docs define wider enum model |
| E4-T02 | partial | openapi.yaml; Frontend/src/api.ts; backend-ui-bridge/server.js | compile request contract updated for review_state/bridge_metadata | frontend build only (no contract assertion) | CMD-04, CMD-15 | response-side semantics not fully modeled; no backward-compat adapter tests | docs claim full contract migration |
| E4-T03 | not_implemented | none | no UI component references for policy semantics rendering | none | CMD-13 | no legal confirmation/residual uncertainty UI | docs specify component work absent |
| E5-T01 | partial | contracts/vendors/canonical_vendors.json; app.py; backend-ui-bridge/server.js | canonical registry load/snapshot; alias mapping | test_vendor_names_from_intent_are_preserved_in_scoring_and_report | CMD-02, CMD-08, CMD-12 | unknown alias hard reject not strict; manifest registry hash binding absent | docs claim stronger registry enforcement |
| E5-T02 | partial | app.py; tests/test_admin_console.py | _vendor_identity_key; _vendor_from_registry; STALE_VENDOR_ALIAS_PRESENT | test_vendor_names_from_intent_are_preserved_in_scoring_and_report | CMD-02, CMD-09 | product-label normalization not implemented | docs include vendor/product normalization |
| E5-T03 | partial | app.py; contracts/vendors/canonical_vendors.json; Frontend/src/MultiRoleGovernedCompilePanel.tsx | evidence freshness_status and max-age config | test_llm_audit_timestamp_override_prevents_stale_freshness_failure | CMD-02, CMD-12 | stale evidence is warning-only; no class-specific thresholds | docs claim freshness gating |
| E5-T04 | partial | app.py; tests/test_admin_console.py | selected-vendor support count checks | none direct | CMD-09, CMD-12 | no security/pricing/operational class completeness gates/tests | docs expect class-complete dossier validation |
| E6-T01 | partial | backend-ui-bridge/server.js; Frontend/src/api.ts; Frontend/src/MultiRoleGovernedCompilePanel.tsx; app.py | bridge default removal in compile path; replay legacy defaults remain | test_inline_payload_preserves_intent_without_default_overwrite | CMD-02, CMD-12 | /verify/replay still injects deterministic-governance/llm-hallucination-risk/auto-ref | docs claim no default overwrite; legacy path contradicts |
| E6-T02 | partial | backend-ui-bridge/server.js; app.py; openapi.yaml; Frontend/src/api.ts | bridge_metadata namespace added and persisted | test_inline_payload_preserves_intent_without_default_overwrite (indirect) | CMD-12, CMD-15 | llm_provider still travels outside bridge_metadata; no isolation test | docs claim strict provenance separation |
| E6-T03 | partial | app.py; tests/test_admin_console.py | _target_preserved; intent target checks; hard gates for missing constraints/targets | indirect only | CMD-09, CMD-12 | no pointer-level intent map; omission negatives incomplete | docs require deterministic intent-to-output mapping |
| E6-T04 | not_implemented | none | no provider-metadata differential suite | none | CMD-13, CMD-16 | recommendation invariance not proven | docs require differential tests |
| E7-T01 | not_implemented | none | tests/golden absent | none | CMD-14 | no golden fixtures/snapshots | docs require golden suite |
| E7-T02 | partial | tests/test_admin_console.py; app.py | some hard-gate negatives implemented | test_compile_hard_gate_rejects_unresolved_evidence_and_non_measurable_metrics; test_high_assurance_requires_completed_review_state | CMD-02, CMD-09 | not one negative per hard gate; tests/negative absent | docs require full negative fixture suite |
| E7-T03 | partial | tests/test_admin_console.py; scripts_e2e_runtime_smoke.py; scripts_e2e_assurance_validation.py | /verify/replay path exercised; e2e replay checks | test_replay_verification_certificate_for_deterministic_execution | CMD-02, CMD-05, CMD-06 | no drift mutation test; replay path still has legacy fallbacks | docs require drift-safe replay regression |
| E7-T04 | partial | .github/workflows/ci.yml; scripts_production_readiness_check.py; scripts/verify_decision_pack.js | CI includes smoke/readiness; verifier script exists | none explicit as dedicated CI asserts | CMD-05, CMD-06, CMD-07, CMD-08, CMD-14 | no explicit trust-mode matrix; offline verifier not dedicated mandatory CI gate | docs require explicit trust/sign-verify CI gates |
| E7-T05 | not_implemented | none | no bridge/runtime parity contract tests | none | CMD-11, CMD-15, CMD-16 | endpoint contract drift detection missing | docs require parity suite |
| E8-T01 | partial | app.py; openapi.yaml; Frontend/src/api.ts | review_state schema and artifact emission | test_high_assurance_requires_completed_review_state | CMD-02, CMD-08, CMD-15 | schema validation shallow; persistence migration coverage absent | docs expect stronger schema/persistence guarantees |
| E8-T02 | partial | app.py; tests/test_admin_console.py | REVIEW_STATE_INCOMPLETE gate for high assurance | test_high_assurance_requires_completed_review_state | CMD-02, CMD-09 | no RBAC-backed reviewer identity workflow; no ledger review event linkage | docs include workflow/RBAC path |
| E8-T03 | partial | app.py | review_state embedded in board report and decision summary | none | CMD-08, CMD-12 | no dedicated exceptions/waivers section with rationale/approver; no UI render | docs expect board/UI rendering |
| E8-T04 | not_implemented | none | no review/approval event append path in trust ledger | none | CMD-12, CMD-16 | immutable approval event chain absent | docs require approval event logging |

## Specific Area Assessment (A-H)

| area | status | assessment |
|---|---|---|
| A Trust model hardening | partial | Non-dev ephemeral/signing blocks and sign/verify gates exist; bridge/runtime trust parity and startup error taxonomy remain incomplete. |
| B Claim/evidence graph hardening | partial | Hard gates exist, but evidence schema validation and full vendor alignment tests are incomplete. |
| C Board report completeness | partial | Required sections/gates exist; direct missing-section negative coverage and substance-quality checks are incomplete. |
| D Policy semantics uplift | partial | Runtime fields exist; frontend rendering and response contract exposure are incomplete. |
| E Vendor normalization and freshness | partial | Canonical registry and mismatch gates exist; stale evidence and dossier-class completeness gates are incomplete. |
| F Human intent preservation | partial | Bridge defaults removed on compile path; replay path still injects legacy defaults. |
| G Verification/replay/golden/negative testing | partial | Core tests pass; golden and negative fixture suites/parity tests are incomplete or absent. |
| H Human review/accountability | partial | Review-state schema and high-assurance gate exist; ledger approval events and UI/board waiver rendering are missing. |

## Overall Verdict (Required)

| epic | verdict |
|---|---|
| Epic 1 | Partially implemented |
| Epic 2 | Partially implemented |
| Epic 3 | Partially implemented |
| Epic 4 | Partially implemented |
| Epic 5 | Partially implemented |
| Epic 6 | Partially implemented |
| Epic 7 | Partially implemented |
| Epic 8 | Partially implemented |

## Top 10 Remaining Blockers

1. Legacy fallback defaults remain in `app.py` `/verify/replay` (`deterministic-governance`, `llm-hallucination-risk`, `auto-ref-*`).
2. Bridge trust checks are weaker than runtime trust checks for key registry match.
3. `tests/golden` fixture suite is absent.
4. `tests/negative` fixture suite is absent and hard-gate negative coverage is incomplete.
5. Policy semantics are not rendered in frontend components.
6. OpenAPI response schemas do not fully expose runtime policy/trust semantics.
7. Stale critical evidence is not a hard-fail gate.
8. Selected-vendor dossier checks are not class-complete (security/pricing/operational).
9. No immutable ledger event chain for review/approval lifecycle.
10. No bridge/runtime parity contract test suite.

## Exact Next Actions

1. Patch `app.py` `verify_replay()` to remove business-semantic fallback defaults and use explicit missing-input markers.
2. Add key-registry presence/match validation in `backend-ui-bridge/server.js` non-dev startup path.
3. Create `tests/golden` snapshots for `board_report.json`, `governance_manifest.json`, and `signed_export.sigmeta.json`.
4. Create `tests/negative` fixtures with one failure test per hard gate code.
5. Extend `openapi.yaml` response schemas for policy semantics and trust readiness fields.
6. Implement frontend rendering for `assessment_mode`, `assurance_level`, `compliance_position`, `legal_confirmation_required`, `residual_uncertainty`.
7. Promote stale critical evidence from warning to hard gate with class-aware thresholds.
8. Add class-complete selected-vendor dossier validation and dedicated negative tests.
9. Implement review/approval endpoints that append immutable ledger events.
10. Add bridge/runtime parity integration tests for `/health`, `/trust/status`, `/admin/config/effective`, `/api/governed-compile`.

## Files/Symbols Most Likely Needing Further Work

- `app.py:verify_replay()`
- `app.py:_build_execution()` freshness/dossier gate block
- `app.py:hard_gate_failures` assembly block
- `backend-ui-bridge/server.js:loadSigningKeyPair()`
- `backend-ui-bridge/server.js:/api/llm-governed-compile`
- `openapi.yaml` response schemas
- `Frontend/src/api.ts` policy/trust response typing
- `Frontend/src/*` policy semantics viewers
- `tests/test_admin_console.py` hard-gate negative coverage
- `.github/workflows/ci.yml` explicit trust/sign-verify jobs

## Verification Command Catalog

- CMD-01: `git rev-parse --short HEAD`
- CMD-02: `python -m pytest -q --basetemp .pytest_tmp`
- CMD-03: `node --check backend-ui-bridge/server.js`
- CMD-04: `npm --prefix Frontend run build`
- CMD-05: `python scripts_e2e_runtime_smoke.py`
- CMD-06: `python scripts_e2e_assurance_validation.py`
- CMD-07: `python scripts_production_readiness_check.py`
- CMD-08: `node scripts/verify_decision_pack.js artifacts/bc5ea544-7c75-5943-a840-3562fd7fa4a5 contracts/keys/public_keys.json`
- CMD-09: `rg -n "hard_gate_failures|compile_quality_gate_failed|PLACEHOLDER_CLAIM_ID_PRESENT|UNRESOLVED_EVIDENCE|VENDOR_EVIDENCE_MISMATCH|COMPETITOR_PRIMARY_EVIDENCE|INVALID_SUCCESS_METRICS|MISSING_REGULATORY_CONSTRAINTS|MISSING_SUCCESS_TARGETS|DECISION_PROVENANCE_INCONSISTENT|POLICY_EVIDENCE_BASIS_MISSING|BOARD_SECTION_INCOMPLETE|REVIEW_STATE_INCOMPLETE|STALE_VENDOR_ALIAS_PRESENT" app.py`
- CMD-10: `rg -n "TRUST_REGISTRY_DEV_AUTOREGISTER|allow_registry_autoregister|Non-development runtime requires SIGNING_PRIVATE_KEY_PEM|not present in contracts/keys/public_keys.json|does not match registered public key material" app.py`
- CMD-11: `rg -n "ephemeral_dev_only|Non-development bridge runtime requires SIGNING_PRIVATE_KEY_PEM|key_registry_ok|trust_registry_source" backend-ui-bridge/server.js`
- CMD-12: `rg -n "deterministic-governance|llm-hallucination-risk|auto-ref-|INLINE_ROLE_PAYLOAD_USED|fallback_evidence_ids|unresolved-evidence|intent_coverage|review_state|bridge_metadata" app.py backend-ui-bridge/server.js`
- CMD-13: `rg -n "assessment_mode|assurance_level|compliance_position|legal_confirmation_required|residual_uncertainty" app.py Frontend/src openapi.yaml`
- CMD-14: `if (Test-Path tests/golden) { Write-Output 'tests/golden:present' } else { Write-Output 'tests/golden:absent' }; if (Test-Path tests/negative) { Write-Output 'tests/negative:present' } else { Write-Output 'tests/negative:absent' }; if (Test-Path .github/workflows) { Get-ChildItem .github/workflows -File | Select-Object -ExpandProperty Name } else { Write-Output '.github/workflows:absent' }`
- CMD-15: `rg -n "requested_assurance_level|review_state|bridge_metadata|assessment_mode|assurance_level|compliance_position" openapi.yaml Frontend/src/api.ts`
- CMD-16: `rg -n "^def test_" tests/test_admin_console.py`
