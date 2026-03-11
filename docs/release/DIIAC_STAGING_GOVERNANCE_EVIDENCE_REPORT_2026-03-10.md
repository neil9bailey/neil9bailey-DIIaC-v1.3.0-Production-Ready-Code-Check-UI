# DIIaC Staging Governance Evidence Report (2026-03-10)

> Superseded after clean reset/rebuild by: `docs/release/DIIAC_STAGING_GOVERNANCE_EVIDENCE_REPORT_2026-03-10_POST_RESET.md`

## Scope and Context

- Repository: `F:\code\diiac\diiac_v1.2.1_codex`
- Git remote: `https://github.com/neil9bailey/neil9bailey-DIIaC-v1.2.1-Production-Ready-Code-Check-UI.git`
- Assessed commit on `main`: `4c737ae` (policy-pack gates, deterministic input freeze, role idempotency)
- Evidence capture timestamp (UTC): 2026-03-10 02:27 to 02:29
- Runtime endpoints assessed:
  - `http://localhost:8100` (governance runtime)
  - `http://localhost:3101` (backend-ui-bridge)

Evidence files are stored in:

- `docs/release/evidence/2026-03-10-copilot-governance/`

## Executive Assessment

**Current verdict: Partially ready, not yet full production customer-ready.**

The stack is healthy, Entra auth is active, Copilot-only provider mode is active, and signed decision packs are produced with merkle evidence. However, the three latest decision packs show evidence-quality warnings (including stale/missing LLM freshness and zero strong refs) while still returning `decision_status: recommended`. Exported packs also do not include the newly expected deterministic replay artifacts.

This is a governance assurance gap that should be closed before claiming full auditor-grade deterministic operation.

## What Is Proven by Current Evidence

### 1) Identity and provider controls are active in staging

From `bridge_auth_status.json`:

- `auth_mode: entra_jwt_rs256`
- `entra_enabled: true`
- `llm_provider_mode: copilot_only`

This proves staging is operating with Entra JWT auth and Copilot-only provider lock.

### 2) Runtime governance services are healthy

From `runtime_health.json`:

- `status: OK`
- `overall_ready: true`
- readiness checks include `policy_packs_loaded: true`, `signing_trust_ready: true`, and storage/database checks all `true`.

### 3) Policy-pack and evidence-gate configuration is loaded

From `runtime_admin_config.json`:

- `policy_pack_enforce: true`
- `policy_packs: ["eu_ai_act_deployer_v1", "uk_ai_governance_v1"]`
- evidence gate config:
  - `min_strong_refs: 2`
  - `min_claim_coverage: 0.6`
  - `require_fresh_llm: true`

### 4) Three governed decision packs were generated and signed

From `decision_pack_inventory.json` and each zipped pack:

- Pack IDs:
  - `decision-pack_4b256648-fe62-5dda-ae05-752b57f2ee26.zip`
  - `decision-pack_d62cc2fe-8e15-5cf0-b884-4ea4f20f62af.zip`
  - `decision-pack_69f3da67-8c39-5b94-bc6a-8096c5c6118f.zip`
- All packs include signature files:
  - `signed_export.sig`
  - `signed_export.sigmeta.json`
- All packs include merkle manifest data (`governance_manifest.json`) and Copilot provenance in board report (`llm_provider: Copilot`).

## Critical Findings and Gaps

### A) Evidence-quality gating is not yet reflected in final recommendation status

Observed across all three packs:

- `evidence_strong_refs_count: 0`
- freshness state not passing:
  - `STALE` or `MISSING_OR_INVALID`
- accuracy warnings are present, including stale/missing timestamp warnings
- yet `decision_status` remains `recommended`

**Risk:** This can undermine claims of deterministic governance enforcement because low-quality evidence should produce a non-pass recommendation state (for example `needs_more_evidence`) before board acceptance.

### B) New deterministic replay/policy artifacts are missing from exported packs

Expected from v1.2.1 governance-layer model but not present in these 3 exports:

- `policy_pack_compliance.json` (missing)
- `replay_certificate.json` (missing)
- `deterministic_input_snapshot.json` (missing)

**Risk:** Auditor replayability and policy-proof traceability are reduced in exported evidence packs.

### C) Version metadata drift

From `runtime_admin_config.json`:

- `version: v1.2.0`

**Risk:** Release labeling is behind current working intent (`v1.2.1` governance hardening), which can create audit confusion over control baseline provenance.

## What This Means Right Now

- The solution **does prove** Copilot-only operation, Entra enforcement, deterministic packaging/signing, and policy-pack load/enforcement configuration.
- The solution **does not yet prove** that evidence-gate outcomes are deterministically binding recommendation status in final exported packs.
- The solution **does not yet prove** complete replay artifact export for each governed run in the current output set.

## Minimum Acceptance Criteria to Reach Customer-Ready Claim

1. Re-run the 3-role UI E2E on the latest containers after a full image rebuild and verify packs include:
   - `deterministic_input_snapshot.json`
   - `replay_certificate.json`
   - `policy_pack_compliance.json`
2. Confirm low-evidence runs do not return `recommended` when freshness/strong-ref thresholds fail.
3. Confirm `version` metadata is aligned to released governance baseline.
4. Re-capture `sha256_manifest.txt` and retain as release evidence.

## Evidence Inventory

Primary files:

- `docs/release/evidence/2026-03-10-copilot-governance/git_status.txt`
- `docs/release/evidence/2026-03-10-copilot-governance/git_log_latest.txt`
- `docs/release/evidence/2026-03-10-copilot-governance/runtime_health.json`
- `docs/release/evidence/2026-03-10-copilot-governance/bridge_auth_status.json`
- `docs/release/evidence/2026-03-10-copilot-governance/runtime_admin_config.json`
- `docs/release/evidence/2026-03-10-copilot-governance/decision_pack_inventory.json`
- `docs/release/evidence/2026-03-10-copilot-governance/sha256_manifest.txt`
- `exports/decision-pack_4b256648-fe62-5dda-ae05-752b57f2ee26.zip`
- `exports/decision-pack_d62cc2fe-8e15-5cf0-b884-4ea4f20f62af.zip`
- `exports/decision-pack_69f3da67-8c39-5b94-bc6a-8096c5c6118f.zip`

