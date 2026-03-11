# DIIaC Staging Governance Evidence Report (Post-Reset, 2026-03-10)

## Scope

- Repository: `F:\code\diiac\diiac_v1.2.1_codex`
- Stack reset/rebuild: completed with `docker compose -f docker-compose.yml -f docker-compose.staging.yml down --volumes` then `up --build -d`
- This report supersedes the earlier pre-reset assessment for the same date.

## Fixes Applied in This Cycle

- `backend-ui-bridge/server.js`
  - legacy `/govern/decision` retired by default (`410`) unless explicitly re-enabled via env flag
  - decision-pack export now runtime-first by default (local bridge artifact fallback disabled unless explicitly enabled)
- `app.py`
  - runtime admin config version updated to `v1.2.1`
- `Frontend/src/App.tsx`
  - removed legacy exploratory panel from primary UI flow to prevent non-governed path confusion

## Fresh Environment Verification

- Runtime health: `OK`, `ledger_record_count: 0` immediately after reset
- Runtime config:
  - `version: v1.2.1`
  - `policy_pack_enforce: true`
  - `policy_packs: [eu_ai_act_deployer_v1, uk_ai_governance_v1]`
  - evidence gates: `min_strong_refs=2`, `min_claim_coverage=0.6`, `require_fresh_llm=true`
- Bridge auth status:
  - `auth_mode: entra_jwt_rs256`
  - `llm_provider_mode: copilot_only`

## Validation Runs

Four fresh runs were executed in the clean environment:

- Positive (CIO): `0dad1182-bba2-5498-bf7e-0ec233b20135`
  - `decision_status: recommended`
  - `quality_gate_failures: []`
- Positive (CSO): `ad9b6d0f-86a8-51f5-abb1-76925b6f7f04`
  - `decision_status: recommended`
  - `quality_gate_failures: []`
- Positive (ACTING_CTO): `8d3d7644-366d-53ea-9240-f2f43087f4a9`
  - `decision_status: recommended`
  - `quality_gate_failures: []`
- Negative gate control test: `6ab1858e-bd1b-5c83-805a-6d69c57684a0`
  - `decision_status: not_recommended`
  - failed gates included strong-ref minimum and stale LLM freshness

## Artifact Completeness Verification

For all fresh runs, exported decision packs include:

- `deterministic_input_snapshot.json`
- `policy_pack_compliance.json`
- `replay_certificate.json`
- signatures (`signed_export.sig`, `signed_export.sigmeta.json`)
- governance manifest and trace files

## Verdict

**Staging governance pipeline is now stable and production-customer-ready for governed compile operation on the current build baseline**, with deterministic gates and policy-pack enforcement behaving as intended in clean-state runs.

Residual operational note:

- Full UI sign-in/user-journey acceptance should still be completed by business UAT (Entra-authenticated browser workflow), but core governance engine and staging container behavior are now validated and consistent.

## Evidence Location

- `docs/release/evidence/2026-03-10-post-reset-copilot-governance/`
- Key machine-readable run summary:
  - `validation_runs.json`
