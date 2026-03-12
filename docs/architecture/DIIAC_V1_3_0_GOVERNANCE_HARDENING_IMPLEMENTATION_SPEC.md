# DIIaC v1.3.0 Governance Hardening Implementation Spec

Date: 2026-03-12
Status: Implementation Ready
Audience: Runtime, Bridge, Frontend, Security, QA, Release Engineering

## 1. Objective and Constraints

This spec defines the implementation program to harden DIIaC as governed decision infrastructure without changing the core architecture:

- human intent in
- governed compilation
- deterministic scoring and transformation
- evidence-bound outputs
- signed export artifacts
- replayable audit trail
- policy-pack enforcement
- Merkle and integrity verification

Non-goals:

- no conversion into generic chat workflow tooling
- no weakening of deterministic behavior
- no cosmetic-only work that does not improve governance correctness

## 2. Baseline Classification

### 2.1 Verified code facts (from current repo)

| Fact ID | Verified code fact | Evidence location |
|---|---|---|
| VF-01 | Runtime signing key loader returns generated ephemeral Ed25519 key when `SIGNING_PRIVATE_KEY_PEM` is absent. | `app.py` `_load_or_create_signing_key()` |
| VF-02 | Non-dev startup blocks ephemeral signing, but ephemeral fallback path exists in core loader and is active in dev. | `app.py` startup trust checks |
| VF-03 | Runtime can auto-register and rewrite `contracts/keys/public_keys.json` in dev mode (`allow_registry_autoregister`). | `app.py` key registry normalization and write path |
| VF-04 | Bridge creates ephemeral keypair when no private key is configured and bootstraps `public_keys.json` when missing. | `backend-ui-bridge/server.js` `loadOrCreateSigningKeyPair()` and `PUBLIC_KEYS_PATH` bootstrap |
| VF-05 | Bridge compile payload injects defaults `non_negotiables: ["deterministic-governance"]` and `risk_flags: ["llm-hallucination-risk"]`. | `backend-ui-bridge/server.js` `/api/llm-governed-compile` payload builder |
| VF-06 | Required board sections are currently enforced via placeholder insertion, not hard compile fail. | `app.py` `_enforce_sections()` |
| VF-07 | Report completeness failures currently degrade recommendation status but do not stop compile/export. | `app.py` report completeness block |
| VF-08 | Evidence objects exist but are minimal and do not implement full evidence schema required for board/regulatory scrutiny. | `app.py` evidence object construction |
| VF-09 | Policy semantics currently use control-signal model (`assessment_mode`, `assurance_level`, `compliance_position`) but not target enum model. | `app.py` policy pack control result construction |
| VF-10 | Frontend/OpenAPI contract does not yet expose stronger assessment semantics and review accountability fields end-to-end. | `Frontend/src/api.ts`, `openapi.yaml` |

### 2.2 Inferred risks (derived from facts)

| Risk ID | Inferred risk | Derived from |
|---|---|---|
| IR-01 | Trust behavior differs across runtime and bridge, increasing audit and attack-surface ambiguity. | VF-01, VF-03, VF-04 |
| IR-02 | Dev auto-registration can normalize unsafe operational habits and hide registry drift until late. | VF-03 |
| IR-03 | Placeholder section behavior can produce structurally valid but decision-useless artifacts. | VF-06, VF-07 |
| IR-04 | Claim/evidence linkage remains weak against high-assurance due diligence because evidence semantics are shallow. | VF-08 |
| IR-05 | Policy language can still be misread as stronger compliance posture than supported evidence. | VF-09, VF-10 |
| IR-06 | Bridge defaults can dilute real business intent and create governance-intent mismatch. | VF-05 |
| IR-07 | Human accountability is not enforced as a first-class gating primitive for high assurance outputs. | VF-10 |

### 2.3 Proposed remediation posture

- Implement eight epics below in three waves.
- Introduce hard fail quality gates in compile/export path.
- Preserve deterministic/replay architecture while separating trust anchor responsibilities.

## 3. Prioritization Model

| Priority | Meaning | SLA expectation |
|---|---|---|
| P0 | Release blocker for governed production use. | Must complete in Wave 1 |
| P1 | High-assurance uplift needed before board/regulatory-grade claims. | Must complete by Wave 2 |
| P2 | Highest-grade finish and operability enhancements. | Complete in Wave 3 |

## 4. Epic Backlog

## Epic 1 - Trust model hardening

Goal: Separate signer, trust registry, and verifier with externally anchored production trust.

### E1-T01 Remove runtime trust-registry mutation from operational paths

Priority: P0
Impacted modules: `app.py`, `contracts/keys/public_keys.json`, `tests/test_admin_console.py`, `scripts_production_readiness_check.py`

Scope:
- Remove runtime write/update behavior for `contracts/keys/public_keys.json` in all non-dev environments.
- Make dev auto-registration opt-in (`TRUST_REGISTRY_DEV_AUTOREGISTER=true`) and default off.
- Replace reconciliation logic with explicit startup error taxonomy.

Acceptance criteria:
- Runtime never mutates `contracts/keys/public_keys.json` unless explicit dev opt-in is set.
- Non-dev startup fails if key registry is missing, malformed, or active key mismatch occurs.
- Error responses include deterministic `error_code` values for each failure reason.

Test cases:
- Unit: startup fails on missing registry in non-dev.
- Unit: startup fails on active key mismatch in non-dev.
- Unit: dev runtime with opt-in true may register key; dev runtime with opt-in false does not write file.

### E1-T02 Enforce identical signing mode policy in Python runtime and Node bridge

Priority: P0
Impacted modules: `app.py`, `backend-ui-bridge/server.js`, `Frontend/src/api.ts`

Scope:
- Add shared signing policy contract (`configured`, `ephemeral_dev_only`, `disabled`).
- Bridge startup must reject non-dev ephemeral key mode.
- Expose effective mode on `/health`, `/readiness`, `/admin/config/effective`.

Acceptance criteria:
- Bridge and runtime report the same effective signing policy in non-dev.
- Non-dev bridge startup fails if private key is absent and signing enabled.
- Health/readiness clearly report signer mode and trust source.

Test cases:
- Integration: bridge non-dev startup fails without `SIGNING_PRIVATE_KEY_PEM`.
- Integration: bridge/runtime health responses agree on signing mode.
- Contract: frontend parses and displays aligned trust mode.

### E1-T03 Add production sign-then-verify gate with explicit export blocker

Priority: P0
Impacted modules: `app.py`, `backend-ui-bridge/server.js`, `scripts/verify_decision_pack.js`, `tests/test_admin_console.py`

Scope:
- Keep immediate post-sign verification in compile path and enforce same gate in export bundle route.
- Block export release when signature verification fails or key resolution is ambiguous.
- Add explicit export error taxonomy for trust faults.

Acceptance criteria:
- `/decision-pack/<id>/export` and `/export-signed` both fail on verify mismatch.
- Verify result persisted in signed metadata and audit logs.
- CI test fails if any signed export can be generated with failed verification.

Test cases:
- Negative integration: tampered signature blocks export.
- Negative integration: unknown key ID blocks export.
- Positive integration: configured key signs and verifies successfully.

### E1-T04 Include offline trust bundle and key-history support in decision pack

Priority: P1
Impacted modules: `app.py`, `scripts/verify_decision_pack.js`, `docs/deployment/OFFLINE_VERIFIER_RUNBOOK.md`, `contracts/keys/`

Scope:
- Export `trust_bundle.json` containing active key, historical keys allowed for verification, trust source metadata, and rotation lineage.
- Extend verifier to consume trust bundle first, registry second.
- Support verification of previously signed packs after key rotation.

Acceptance criteria:
- Export contains `trust_bundle.json` for every signed pack.
- Offline verifier can verify old packs using rotated historical keys.
- Trust bundle includes key validity window metadata (`valid_from`, `valid_to`).

Test cases:
- Integration: pack signed with old key verifies after key rotation.
- Unit: invalid trust bundle schema fails verification.
- E2E: offline verifier passes without external network dependency.

### E1-T05 Trust readiness contract uplift

Priority: P1
Impacted modules: `app.py`, `backend-ui-bridge/server.js`, `openapi.yaml`, `Frontend/src/OperationalDashboard.tsx`

Scope:
- Add trust readiness fields: `signing_mode`, `trust_registry_source`, `trust_registry_mutable`, `historical_keys_loaded`.
- Surface warnings vs blockers cleanly.

Acceptance criteria:
- Readiness payload differentiates advisory warnings from hard blockers.
- UI renders non-dev blocker state clearly.
- OpenAPI reflects fields and enums.

Test cases:
- Contract test for readiness payload schema.
- UI test for blocker rendering.
- Regression test for existing `/health` consumers.

## Epic 2 - Claim/evidence graph hardening

Goal: Bind all material claims to concrete, verifiable evidence objects.

### E2-T01 Semantic claim ID generator

Priority: P0
Impacted modules: `app.py`, `tests/test_admin_console.py`

Scope:
- Replace generic deterministic claim IDs with semantic deterministic IDs using normalized claim text, section, context hash, and vendor scope.
- Guarantee determinism and collision resistance.

Acceptance criteria:
- Claim IDs are stable for same inputs and change only on material claim text changes.
- Claim IDs no longer derive from placeholder fallback identifiers.
- Recommendation claim IDs do not mix with evidence IDs.

Test cases:
- Unit: deterministic ID stability under reorder-safe canonical input.
- Unit: claim text mutation changes ID.
- Regression: existing trace-map endpoint remains functional.

### E2-T02 Evidence object schema v2 implementation

Priority: P0
Impacted modules: `app.py`, `openapi.yaml`, `Frontend/src/api.ts`, `contracts/`

Scope:
- Introduce required evidence object schema fields:
  `evidence_id`, `claim_ids`, `source_type`, `source_title`, `source_uri` or `artifact_ref`, `vendor_scope`, `captured_at`, `effective_date`, `hash`, `freshness_status`, `evidence_strength`, `independence_level`.
- Maintain deterministic canonical serialization for hash and replay stability.

Acceptance criteria:
- Every exported evidence object conforms to schema v2.
- Missing required fields fail compile in non-dev and fail quality gate in dev.
- Evidence hash is reproducible from canonical source descriptor.

Test cases:
- Schema validation test for all exported evidence objects.
- Negative test: missing `captured_at` fails compile.
- Regression: replay hash remains stable for unchanged input.

### E2-T03 Claim to evidence to source validation gate

Priority: P0
Impacted modules: `app.py`, `tests/test_admin_console.py`, `scripts_e2e_runtime_smoke.py`

Scope:
- Enforce full claim binding graph: each material claim must have one or more resolvable evidence objects linked to source descriptor.
- Compile must fail if unresolved claim bindings remain.

Acceptance criteria:
- No `UNRESOLVED` claim bindings in production compile output.
- Compile returns deterministic failure payload with unresolved claim list.
- No placeholder or unresolved URNs in exported artifacts.

Test cases:
- Negative: unresolved claim binding returns 4xx/5xx governed failure.
- Negative: placeholder evidence ref blocks compile.
- Positive: fully bound graph compiles and exports.

### E2-T04 Vendor-evidence alignment gate

Priority: P0
Impacted modules: `app.py`, `contracts/vendors/` (new), `tests/test_admin_console.py`

Scope:
- Add selected-vendor evidence relevance rules:
  primary evidence for selected vendor claims must be first-party or independent non-generated evidence with matching `vendor_scope`.
- Reject competitor documents as primary support for selected vendor claims.

Acceptance criteria:
- Compile fails when selected vendor primary claims are supported by competitor sources.
- At least one first-party and one non-generated independent evidence item required for selected vendor recommendation.
- Gate output names violating claim IDs and evidence IDs.

Test cases:
- Negative: selected vendor = Fortinet, primary evidence from Palo Alto domain fails.
- Negative: generated narrative-only evidence fails primary support gate.
- Positive: mixed first-party + independent support passes.

### E2-T05 Evidence provenance typing

Priority: P1
Impacted modules: `app.py`, `Frontend/src/GovernedReportViewer.tsx`, `Frontend/src/api.ts`

Scope:
- Distinguish `primary_evidence`, `inferred_evidence`, and `generated_narrative` explicitly in evidence bundle and board report.

Acceptance criteria:
- Board report and JSON exports label evidence provenance class for each claim link.
- Policy controls referencing evidence list provenance class and IDs.

Test cases:
- Unit: provenance classes assigned deterministically.
- UI: provenance classes visible in report view.
- Regression: legacy consumers still parse `evidence_trace_map`.

## Epic 3 - Board report quality and completeness gates

Goal: Prevent structurally valid but decision-useless exports.

### E3-T01 Replace placeholder section enforcement with hard-fail policy

Priority: P0
Impacted modules: `app.py`, `tests/test_admin_console.py`, `scripts_e2e_runtime_smoke.py`

Scope:
- Remove placeholder insertion for missing required sections in production path.
- Missing required section triggers compile failure.
- Dev mode may return diagnostics-only preview but must flag non-exportable state.

Acceptance criteria:
- No exported board report contains placeholder section content.
- Production compile fails when required sections are missing.
- Error payload includes missing section names.

Test cases:
- Negative: removed section fails compile with explicit error.
- Negative: placeholder text in any section fails export gate.
- Positive: complete sections compile and export.

### E3-T02 Board-grade required section schema expansion

Priority: P0
Impacted modules: `contracts/business-profiles/*.json`, `app.py`, `openapi.yaml`

Scope:
- Expand required sections to include:
  objectives, recommendation, assumptions, disqualifiers, residual risks, measurable KPIs, regulatory constraints, implementation guardrails, what would change recommendation.
- Validate all required sections are present and non-empty.

Acceptance criteria:
- Profile contracts define required board-grade section set.
- Compile blocks missing or empty required board sections.
- Report completeness status is binary gate, not advisory only.

Test cases:
- Schema test for profile `required_sections` completeness.
- Negative compile test for empty `regulatory constraints` section.
- Positive compile test for all required sections populated.

### E3-T03 Measurable KPI schema and validation

Priority: P0
Impacted modules: `app.py`, `openapi.yaml`, `Frontend/src/MultiRoleGovernedCompilePanel.tsx`

Scope:
- Add KPI object schema requiring metric name, unit, baseline, target, timeframe, and tolerance.
- Reject principle-only metrics without measurable targets.

Acceptance criteria:
- Success metrics in exports are structured KPI objects.
- Non-measurable success metrics fail compile/export.
- Intent explicit targets map to KPI targets where applicable.

Test cases:
- Negative: `privacy-by-design` only metric fails.
- Negative: missing baseline/target fails.
- Positive: cycle-time reduction KPI passes.

### E3-T04 Intent coverage preservation gate

Priority: P0
Impacted modules: `app.py`, `backend-ui-bridge/server.js`, `tests/test_admin_console.py`

Scope:
- Add intent preservation map from source inputs to board fields.
- Compile fails when explicit user goals/targets/regulatory constraints are present but not represented in output fields.

Acceptance criteria:
- Export includes `intent_coverage_map` showing source-to-output binding.
- Missing intent coverage for explicit targets blocks recommendation finalization.
- No replacement of user constraints with generic defaults in final recommendation fields.

Test cases:
- Negative: explicit budget ceiling absent from output fails gate.
- Positive: all explicit targets mapped to sections/KPIs.
- Regression: deterministic hash stability preserved.

### E3-T05 Decision basis and provenance consistency validation

Priority: P1
Impacted modules: `app.py`, `tests/test_admin_console.py`

Scope:
- Validate that decision basis statements do not leak template/provider artifacts and align with actual evidence and scoring chain.

Acceptance criteria:
- Decision summary basis references deterministic scoring plus evidence IDs, not provider template leakage.
- Inconsistent provenance statements fail quality gate.

Test cases:
- Negative: provider name appears in selected-vendor rationale without evidence linkage fails.
- Positive: decision basis references claim/evidence/scoring artifacts correctly.

## Epic 4 - Policy semantics uplift

Goal: Represent proof posture accurately and avoid overstated compliance semantics.

### E4-T01 Assessment semantics model v2

Priority: P1
Impacted modules: `app.py`, `contracts/policy-packs/*.json`, `openapi.yaml`

Scope:
- Replace current semantics with structured fields:
  `assessment_mode`, `assurance_level`, `compliance_position`, `legal_confirmation_required`, `evidence_ids`, `residual_uncertainty`.
- Enforce enum set:
  `assessment_mode`: `signal_assessment`, `evidence_backed_assessment`, `independent_reviewed_assessment`.
  `assurance_level`: `generated`, `evidence_backed`, `human_reviewed`, `externally_validated`.
  `compliance_position`: `not_assessed`, `control_signals_satisfied`, `evidence_indicates_alignment`, `legal_confirmation_required`, `externally_confirmed`.

Acceptance criteria:
- Every policy control result emits v2 fields with valid enums.
- `PASS` alone is no longer the top-level semantic communicated to board output.
- Residual uncertainty is explicit when assurance is below externally validated.

Test cases:
- Unit: enum validation for all controls.
- Negative: missing evidence IDs in evidence-backed mode fails.
- Positive: human-reviewed control emits `assurance_level=human_reviewed`.

### E4-T02 Backend and frontend contract migration

Priority: P1
Impacted modules: `openapi.yaml`, `Frontend/src/api.ts`, `Frontend/src/*` policy-related viewers, `backend-ui-bridge/server.js`

Scope:
- Update API schemas and frontend types to consume new semantics.
- Add backward compatibility adapter for historical executions.

Acceptance criteria:
- Frontend renders new semantics without runtime type errors.
- OpenAPI includes new fields and enum docs.
- Historical execution records remain readable.

Test cases:
- Type-check: frontend build passes with strict TS types.
- Contract test: API payload validates against OpenAPI schema.
- Regression: old execution payloads render with compatibility adapter.

### E4-T03 Policy UI semantics rendering

Priority: P1
Impacted modules: `Frontend/src/DerivedCompliancePanel.tsx`, `Frontend/src/GovernanceMetadataPanel.tsx`, `Frontend/src/OperationalDashboard.tsx`

Scope:
- Show proof-level semantics directly in UI.
- Replace any overstated certification language with evidence-position language.

Acceptance criteria:
- UI clearly distinguishes signal-only vs evidence-backed vs external validation.
- Legal confirmation requirement is visibly flagged.

Test cases:
- UI test: legal confirmation badge appears when required.
- UI test: residual uncertainty displayed for non-external states.

## Epic 5 - Vendor normalization and evidence freshness controls

Goal: Ensure selected-vendor dossiers are specific, current, and credible.

### E5-T01 Canonical vendor registry

Priority: P1
Impacted modules: `contracts/vendors/canonical_vendors.json` (new), `app.py`, `backend-ui-bridge/server.js`

Scope:
- Add canonical registry with vendor IDs, aliases, approved domains, active product labels, and effective periods.

Acceptance criteria:
- Compile pipeline resolves vendor names to canonical IDs.
- Unknown vendor aliases are rejected or marked unresolved.
- Registry version/hash recorded in manifest.

Test cases:
- Unit: alias normalization maps known aliases to canonical ID.
- Negative: stale alias rejected.
- Positive: approved domain list loaded and used in gates.

### E5-T02 Vendor/product alias normalization gate

Priority: P1
Impacted modules: `app.py`, `tests/test_admin_console.py`

Scope:
- Normalize vendor and product labels before scoring/reporting.
- Reject outdated product labels when canonical active labels differ.

Acceptance criteria:
- Exported selected vendor/product labels match canonical registry.
- Cross-vendor contamination in rationale is detected and blocked.

Test cases:
- Negative: mismatched product-to-vendor pair fails compile.
- Positive: canonical label substitution deterministic and traceable.

### E5-T03 Evidence freshness evaluator

Priority: P1
Impacted modules: `app.py`, `contracts/vendors/canonical_vendors.json`, `Frontend/src/MultiRoleGovernedCompilePanel.tsx`

Scope:
- Add freshness policies by evidence class (market/pricing/security/documentation).
- Evaluate `captured_at` and `effective_date` against policy thresholds.

Acceptance criteria:
- Freshness status emitted per evidence object.
- Stale critical evidence blocks recommendation finalization.
- Freshness thresholds included in policy metadata.

Test cases:
- Negative: stale pricing evidence triggers gate failure.
- Negative: missing capture date for required evidence class fails.
- Positive: current evidence passes freshness gate.

### E5-T04 Selected-vendor dossier validation

Priority: P1
Impacted modules: `app.py`, `tests/test_admin_console.py`

Scope:
- Require selected-vendor dossier to include aligned security, pricing, and operational evidence set with domain and vendor_scope checks.

Acceptance criteria:
- Recommendation cannot be `recommended` without complete selected-vendor dossier.
- Dossier validation failures are explicit in quality gate output.

Test cases:
- Negative: missing security evidence class fails.
- Negative: source domain not in approved domains fails.
- Positive: dossier complete, aligned, and current passes.

## Epic 6 - Bridge/runtime preservation of human intent

Goal: Preserve source business intent while adding governance constraints.

### E6-T01 Remove bridge default overwrite behavior

Priority: P0
Impacted modules: `backend-ui-bridge/server.js`, `Frontend/src/api.ts`, `Frontend/src/MultiRoleGovernedCompilePanel.tsx`, `app.py`

Scope:
- Stop unconditional bridge defaults for `non_negotiables` and `risk_flags`.
- Accept and forward user-supplied `non_negotiables`, `risk_flags`, `goals`, `regulatory_context`, `success_targets`.

Acceptance criteria:
- User-provided constraints are preserved exactly unless rejected by validation.
- When values are absent, bridge marks `missing_user_input` metadata instead of injecting business semantics.
- Compile output includes preserved intent fields.

Test cases:
- Integration: provided constraints arrive unchanged in runtime role bundle.
- Integration: absent constraints produce explicit missing-input markers, not injected defaults.
- Regression: existing compile endpoint still works with minimal payload.

### E6-T02 Add `bridge_metadata` namespace and provenance separation

Priority: P0
Impacted modules: `backend-ui-bridge/server.js`, `app.py`, `openapi.yaml`, `Frontend/src/api.ts`

Scope:
- Store provider and bridge operational metadata under `bridge_metadata`.
- Keep decision fields free from provider/template leakage.

Acceptance criteria:
- `llm_provider`, bridge timestamp, request mode exist only in `bridge_metadata` unless explicitly required elsewhere.
- Recommendation fields do not include provider branding unless sourced evidence requires it.

Test cases:
- Unit: payload transformer routes metadata to namespace.
- Negative: provider leakage into `selected_vendor` or decision basis fails gate.

### E6-T03 Intent-to-structured-output coverage validator

Priority: P0
Impacted modules: `app.py`, `tests/test_admin_console.py`

Scope:
- Add deterministic mapping checks between user intent fields and structured output fields.
- Gate compile when stated goals/regulatory constraints/targets are omitted from output model.

Acceptance criteria:
- `intent_coverage_map` exported with source and target pointers.
- Missing mapping for explicit input fields triggers hard gate.

Test cases:
- Negative: explicit regulatory mention with empty regulatory constraints fails.
- Negative: explicit success targets with empty target mapping fails.
- Positive: complete mapping passes and is replay-stable.

### E6-T04 Provider-vendor rationale isolation tests

Priority: P1
Impacted modules: `tests/` (new bridge-runtime integration tests), `backend-ui-bridge/server.js`, `app.py`

Scope:
- Add integration tests to ensure provider provenance never changes deterministic vendor recommendation fields.

Acceptance criteria:
- Changing provider metadata alone does not change deterministic ranking/recommendation given same governed inputs.

Test cases:
- Differential test: same role bundle, different provider metadata, identical scoring outputs.

## Epic 7 - Verification, replay, and golden artifact testing

Goal: Make outputs reproducible, testable, and independently checkable.

### E7-T01 Golden export fixture suite

Priority: P0
Impacted modules: `tests/golden/` (new), `tests/test_admin_console.py`, `scripts/verify_decision_pack.js`

Scope:
- Add canonical golden fixtures for board reports, manifests, signatures, and evidence maps.
- Include deterministic canonicalization rules for tolerated variance fields.

Acceptance criteria:
- Golden suite validates deterministic content and excludes approved volatile fields only.
- CI fails on meaningful artifact drift.

Test cases:
- Snapshot test: board report JSON/markdown match golden fixture.
- Snapshot test: manifest and signature payload match golden fixture.

### E7-T02 Negative artifact quality suite

Priority: P0
Impacted modules: `tests/negative/` (new), `app.py`

Scope:
- Add explicit failing fixtures for each hard quality gate violation.

Acceptance criteria:
- Every hard gate has at least one negative test proving compile/export failure.
- Failure payload includes deterministic `error_code` and violating item IDs.

Test cases:
- Placeholder claim IDs present.
- Unresolved evidence.
- Vendor-evidence mismatch.
- Incomplete board sections.
- Signature verification failure.

### E7-T03 Replay regression suite

Priority: P0
Impacted modules: `tests/test_admin_console.py`, `scripts_e2e_runtime_smoke.py`, `scripts_e2e_assurance_validation.py`

Scope:
- Extend replay tests to include evidence graph and policy semantics fields.
- Verify replay determinism under fixed input snapshot.

Acceptance criteria:
- Replay cert validates equality of core deterministic artifacts across reruns.
- Drift in governed fields fails replay checks.

Test cases:
- Positive replay equality test.
- Negative replay drift test with controlled mutation.

### E7-T04 Trust-mode and sign/verify CI gates

Priority: P0
Impacted modules: `.github/workflows/` (new or updated), `scripts_production_readiness_check.py`, `scripts/verify_decision_pack.js`

Scope:
- Add CI jobs for dev trust mode, non-dev strict trust mode, sign/verify gate, and export verification.

Acceptance criteria:
- CI blocks merge when trust mode policy violated.
- CI blocks merge when offline verifier fails on generated pack.

Test cases:
- Pipeline test matrix: dev, staging/prod simulation.
- Pipeline test: non-dev ephemeral signing must fail.

### E7-T05 Bridge/runtime parity contract tests

Priority: P1
Impacted modules: `tests/` (new integration suite), `backend-ui-bridge/server.js`, `app.py`

Scope:
- Add parity tests for trust fields, compile payload mapping, and policy semantics shape.

Acceptance criteria:
- Bridge and runtime contracts stay aligned across versions.

Test cases:
- Contract diff test for key endpoints (`/health`, `/readiness`, compile response).

## Epic 8 - Human review and approval accountability

Goal: High-assurance outputs include explicit accountable human review state.

### E8-T01 Review-state schema extension

Priority: P2
Impacted modules: `app.py`, `openapi.yaml`, `Frontend/src/api.ts`, `persistence.py`

Scope:
- Add fields:
  `human_review_required`, `human_review_completed`, `reviewed_by`, `approved_by`, `review_timestamps`, `open_exceptions`, `waived_controls`.
- Persist review state in execution record and export artifacts.

Acceptance criteria:
- High-assurance exports include review-state object.
- Schema validation fails if review-state fields malformed.

Test cases:
- Unit: schema validation for review-state object.
- Integration: review-state persisted and returned by execution endpoints.

### E8-T02 Assurance gating by review completion

Priority: P2
Impacted modules: `app.py`, `backend-ui-bridge/auth/rbac.js`, `tests/test_admin_console.py`

Scope:
- Require explicit human review completion before setting high assurance levels (`human_reviewed`, `externally_validated`).

Acceptance criteria:
- High assurance cannot be emitted with `human_review_completed=false`.
- Gate failure includes missing reviewer/approver metadata.

Test cases:
- Negative: assurance level upgrade without review completion fails.
- Positive: approved review state enables high assurance output.

### E8-T03 Board rendering of exceptions and waivers

Priority: P2
Impacted modules: `app.py`, `Frontend/src/GovernedReportViewer.tsx`

Scope:
- Render open exceptions and waived controls in board report sections and decision summary.

Acceptance criteria:
- Board report includes explicit exceptions/waivers section when present.
- Waived controls include rationale and approver identity.

Test cases:
- UI test: waived controls visible with approver.
- Export test: exceptions serialized in board report JSON and markdown.

### E8-T04 Approval event logging to trust ledger

Priority: P2
Impacted modules: `app.py`, `persistence.py`, `tests/test_admin_console.py`

Scope:
- Add ledger events for review completion and approval decisions with signer identity and timestamps.

Acceptance criteria:
- Review/approval actions append immutable ledger records.
- Audit export includes these events.

Test cases:
- Integration: approval action creates ledger event.
- Audit test: ledger slice contains review event chain.

## 5. Hard Quality Gates (Compile/Export must fail)

These are mandatory blockers in non-dev and mandatory failing tests in all environments.

| Gate ID | Failure condition | Enforcement stage | Expected failure code |
|---|---|---|---|
| QG-01 | Placeholder claim IDs present | compile | `PLACEHOLDER_CLAIM_ID_PRESENT` |
| QG-02 | Unresolved evidence exists | compile | `UNRESOLVED_EVIDENCE` |
| QG-03 | Selected-vendor evidence misaligned | compile | `VENDOR_EVIDENCE_MISMATCH` |
| QG-04 | Competitor docs used as primary support | compile | `COMPETITOR_PRIMARY_EVIDENCE` |
| QG-05 | Empty or non-measurable success metrics | compile | `INVALID_SUCCESS_METRICS` |
| QG-06 | Regulation mentioned but regulatory constraints empty | compile | `MISSING_REGULATORY_CONSTRAINTS` |
| QG-07 | Goals/targets present but success targets empty | compile | `MISSING_SUCCESS_TARGETS` |
| QG-08 | Decision basis/provenance inconsistent | compile | `DECISION_PROVENANCE_INCONSISTENT` |
| QG-09 | Missing trust registry in non-dev | startup | `TRUST_REGISTRY_MISSING` |
| QG-10 | Ephemeral signing in non-dev | startup | `NONDEV_EPHEMERAL_SIGNING_BLOCKED` |
| QG-11 | Signature verification fails | compile/export | `SIGNATURE_VERIFICATION_FAILED` |
| QG-12 | Policy control lacks required evidence basis | compile | `POLICY_EVIDENCE_BASIS_MISSING` |
| QG-13 | Required board section incomplete | compile | `BOARD_SECTION_INCOMPLETE` |
| QG-14 | Human review required but incomplete for high assurance | compile/export | `REVIEW_STATE_INCOMPLETE` |

## 6. Implementation Waves

### Wave 1 - Hard blockers (P0)

Scope:
- Epic 1 tickets E1-T01..E1-T03
- Epic 2 tickets E2-T01..E2-T04
- Epic 3 tickets E3-T01..E3-T04
- Epic 6 tickets E6-T01..E6-T03
- Epic 7 tickets E7-T01..E7-T04

Wave 1 exit criteria:
- QG-01 through QG-13 enforced.
- Non-dev trust cannot self-heal or use ephemeral signing.
- Placeholder section and unresolved claim/evidence compile paths removed.
- Negative quality suite green with expected failures.

### Wave 2 - Assurance-quality uplift (P1)

Scope:
- Epic 1 tickets E1-T04..E1-T05
- Epic 2 ticket E2-T05
- Epic 4 tickets E4-T01..E4-T03
- Epic 5 tickets E5-T01..E5-T04
- Epic 6 ticket E6-T04
- Epic 7 ticket E7-T05

Wave 2 exit criteria:
- Policy semantics v2 live end-to-end backend to frontend.
- Vendor normalization and freshness gates active.
- Offline trust bundle and key-rotation-safe verification operational.

### Wave 3 - Highest-grade finish (P2)

Scope:
- Epic 8 tickets E8-T01..E8-T04
- Remaining board rendering and operational runbook completion.

Wave 3 exit criteria:
- High assurance outputs require explicit human accountability.
- Review and waiver states are visible in board artifacts and audit chain.
- QG-14 enforced.

## 7. Cross-Epic Test Strategy

| Test layer | Required additions |
|---|---|
| Unit | Signing policy guards, claim ID generator, evidence schema validators, KPI validators, policy enum validators |
| Integration | Bridge-runtime trust parity, compile gate failures, export sign/verify, vendor-evidence alignment, intent coverage mapping |
| E2E | Golden pack generation, replay verification, offline verifier execution, high-assurance review gating |
| CI/CD | Non-dev ephemeral block test, trust registry immutability test, negative quality suite, golden drift detection |

## 8. Definition of Done

Program is complete only when all criteria below are true:

- Core DIIaC architecture remains intact and deterministic.
- Human intent fields are preserved and traceable into structured outputs.
- Governance controls are stronger and implemented as compile/export gates.
- Every material claim is bound to concrete evidence objects meeting schema v2.
- Trust is externally anchored in non-dev with no self-asserting registry mutation.
- Export artifacts are board-grade with no placeholder content.
- Policy semantics communicate proof posture honestly without legal overstatement.
- High-assurance states require explicit human review and approval metadata.
- Hard quality gates QG-01 through QG-14 are enforced and covered by automated tests.
- Golden/replay/offline verification suites pass in CI.

## 9. Execution Notes for Engineering Leads

- Start with Wave 1 P0 blockers in a short-lived hardening branch and merge behind feature flags where needed.
- Keep deterministic canonicalization unchanged unless explicitly versioned and replay-tested.
- Any schema expansion must include migration logic for historical execution records.
- Update runbooks and OpenAPI in the same PRs as behavior changes to prevent contract drift.
