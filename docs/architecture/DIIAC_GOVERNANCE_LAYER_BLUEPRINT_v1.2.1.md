# DIIaC Governance Layer Blueprint v1.2.1

## Purpose

This blueprint defines DIIaC as a provider-agnostic governance layer that wraps LLM-assisted decision workflows with deterministic controls, regulation-aware policy packs, cryptographic proof, and auditor-ready traceability.

The governance layer is authoritative. LLM output is advisory and is only accepted into final recommendations when evidence and policy gates pass.

## Scope

- Runtime: `app.py` (deterministic governance engine)
- Bridge: `backend-ui-bridge/server.js` (Copilot ingestion + governance orchestration)
- UI: `Frontend/src/MultiRoleGovernedCompilePanel.tsx` (role capture and governed compile)
- Policy packs:
  - `contracts/policy-packs/eu_ai_act_deployer_v1.json`
  - `contracts/policy-packs/uk_ai_governance_v1.json`

## Architecture Delta (v1.2.1)

1. Regulation-as-code policy packs are loaded and evaluated during compile.
2. Evidence sufficiency gates now influence decision status.
3. Deterministic input snapshot is frozen and hashed pre-compile.
4. Replay certificate is emitted as a governed artifact.
5. Role input idempotency is enforced to prevent duplicate contamination.
6. Bridge no longer auto-persists role input in compile path; runtime now supports inline role fallback when no persisted context bundle exists.

## Deterministic Governed Compile Flow

1. Collect role evidence (`/api/human-input/role`) with idempotency key.
2. Submit compile request (`/api/llm-governed-compile` -> `/api/governed-compile`).
3. Freeze deterministic input snapshot:
   - execution context
   - profile/schema/R-P policy
   - governance modes
   - role bundle
   - request payload hash and LLM analysis hash
4. Run deterministic scoring and section rendering.
5. Evaluate:
   - business profile control compliance
   - evidence sufficiency gates
   - policy-pack controls (UK/EU)
6. Produce signed artifact set and manifest.
7. Emit replay certificate and append ledger.

## Decision Status Semantics

- `recommended`: profile controls pass and quality gates pass.
- `needs_more_evidence`: profile controls pass but evidence/freshness gates fail.
- `not_recommended`: profile controls or enforced policy-pack controls fail.

This separates governance-control failure from evidence-completeness failure and gives teams precise remediation paths.

## Policy Pack Model

Policy packs are JSON contracts loaded from `contracts/policy-packs/*_v1.json`.

Each control declares:
- `control_id`
- `reference` (legal/guidance mapping)
- `required_signals` (runtime-measured governance signals)

Compile output includes:
- `policy_pack_compliance.json`
- policy summary in `board_report.json` and `down_select_recommendation.json`

## Evidence Quality Gates

Configured via environment variables:

- `EVIDENCE_MIN_STRONG_REFS` (default `2`)
- `EVIDENCE_MIN_CLAIM_COVERAGE` (default `0.6`)
- `EVIDENCE_REQUIRE_FRESH_LLM` (default `true`)
- `LLM_AUDIT_MIN_TIMESTAMP` (default `2025-01-01T00:00:00+00:00`)

Gate failures are surfaced in:
- `accuracy_warnings`
- `quality_gate_failures`
- final `decision_status`

## New/Updated Governed Artifacts

- `deterministic_input_snapshot.json`
- `replay_certificate.json`
- `policy_pack_compliance.json`
- enhanced `down_select_recommendation.json` with:
  - evidence gate outcomes
  - claim coverage
  - policy pack compliance

## Human-in-the-Loop Integrity

Role input endpoint now supports deterministic idempotency:

- duplicate submissions for the same idempotency key are ignored
- response indicates `duplicate_ignored: true`

UI submit/compile buttons now have in-flight locks to reduce accidental duplicate submissions.

## Operational Readiness Signals

`/admin/config` now surfaces:
- active policy packs
- policy-pack enforcement state
- evidence gate configuration

Readiness checks include policy pack presence (`policy_packs_loaded`).

## Auditor Scrutiny Positioning

DIIaC provides:
- deterministic input freeze hash
- execution replay certificate
- signed decision packs
- Merkle-bound artifact lineage
- policy-control pass/fail matrix with references
- explicit evidence-quality gating rationale

This enables auditors to validate not just the output but the governance conditions that allowed the output to be considered recommended.

## Value Once Operational

The platform becomes a reusable governance control plane for any enterprise LLM workflow:

- Customers can keep their preferred LLM providers while enforcing one governance standard.
- Providers can integrate into a trusted assurance layer without owning customer decision governance.
- Regulated enterprises gain machine-checkable, replayable, and cryptographically provable decision governance suitable for external audit and board scrutiny.
