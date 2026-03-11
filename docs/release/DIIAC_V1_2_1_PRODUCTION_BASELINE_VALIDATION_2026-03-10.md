# DIIaC v1.2.1 Production Baseline Validation (Staging)

Date: 2026-03-10
Repository: F:\code\diiac\diiac_v1.2.1_codex
Scope: Copilot-only governed compile baseline, sector-aligned business profiles, deterministic governance integrity, and staging-to-production parity checks.

## 1) Scope Certified

This validation certifies the following baseline configuration for v1.2.1 staging:

- LLM provider mode: Copilot-only.
- Governance runtime: deterministic compile with signing, Merkle, and audit export controls.
- Active business profiles reduced to 5 sector-aligned contracts:
  - `it_enterprise_profile_v1`
  - `it_service_provider_profile_v1`
  - `finance_profile_v1`
  - `healthcare_profile_v1`
  - `transport_profile_v1`
- Removed from active profile set:
  - `national_highways_profile_v1`
  - `national_rail_profile_v1`
  - `tfl_profile_v1`
- UI role selector now includes:
  - `CIO`, `CTO`, `CFO`, `PROCUREMENT`, `CSO`, `ENTERPRISE_ARCHITECT`, `PRINCIPAL_ENGINEER`, `IT_SECTOR_LEAD`

## 2) Functional Corrections Included

- Replay verification hash parity fix in `app.py`:
  - `/verify/replay` now hashes the same normalized deterministic input shape used by governed compile.
  - This removes false replay mismatches caused by raw stored role payload differences.
- Bridge fallback profile defaults aligned with the active contract baseline (5 profiles).
- Regression/test/docs profile count expectations updated from 8 to 5 where baseline checks are executed.

## 3) Validation Commands Executed

All commands were run from `F:\code\diiac\diiac_v1.2.1_codex`.

1. `python -m py_compile app.py`  -> PASS
2. `node --check backend-ui-bridge/server.js`  -> PASS
3. `npm --prefix Frontend run build`  -> PASS
4. `python -m pytest`  -> PASS (`22 passed`)
5. `python scripts_e2e_runtime_smoke.py`  -> PASS
6. `python scripts_production_readiness_check.py`  -> PASS
7. `docker compose -f docker-compose.yml -f docker-compose.staging.yml config`  -> PASS

Notes:
- `docker compose -f docker-compose.staging.yml config` alone is invalid by design in this repo because staging is an override; it must be combined with `docker-compose.yml`.
- Frontend build reports a Vite chunk-size warning (>500 kB). This is non-blocking for runtime correctness but should be optimized post-baseline.

## 4) Engineering Certification Statement

Certification result: PASS (engineering baseline scope)

Based on the checks above, this baseline is certified as production-ready from an engineering controls perspective for customer staging/production emulation, with deterministic governance enforcement active and validated.

Certification covers:
- deterministic compile reproducibility controls,
- signed artifact and verification paths,
- audit export and trust-chain verifiability,
- Copilot-only provider lock behavior,
- profile/role configuration consistency for the approved sector scope.

## 5) Governance and Compliance Position

This certification does not replace legal/compliance sign-off.
It demonstrates that required technical controls for governed AI decision workflows are implemented and operating as tested, including evidence gates, policy-pack enforcement, and traceability outputs suitable for auditor review.

## 6) Evidence Files Touched in This Change Set

- `app.py`
- `backend-ui-bridge/server.js`
- `Frontend/src/MultiRoleGovernedCompilePanel.tsx`
- `contracts/business-profiles/national_highways_profile_v1.json` (removed)
- `contracts/business-profiles/national_rail_profile_v1.json` (removed)
- `contracts/business-profiles/tfl_profile_v1.json` (removed)
- `tests/test_admin_console.py`
- `docs/deployment/DIIAC_CLEAN_BUILD_TEST_VALIDATION_GUIDE.md`
- `docs/release/CHANGELOG.md`

## 7) Freshness Gate Closure (2026-03-10)

Root cause addressed:
- LLM output could include stale `audit_trail.timestamp` values, and freshness gates evaluated this value directly.

Fix implemented:
- Bridge now always stamps a governance-captured UTC timestamp on LLM analysis prior to compile.
- Runtime freshness evaluation now prefers explicit `llm_audit_timestamp` when provided, with traceable source metadata.
- Provider-reported timestamp is preserved for audit transparency but no longer controls freshness when an explicit governance timestamp is present.

Regression evidence:
- `tests/test_admin_console.py::test_llm_audit_timestamp_override_prevents_stale_freshness_failure` (PASS).

## 8) Dashboard Telemetry Clarification

- Operational dashboard intercept trends are sourced from Copilot interception endpoints only:
  - `POST /api/intercept/request`
  - `POST /api/intercept/response`
  - `POST /api/intercept/approval`
- Standard governed compile workflow (`/api/llm-governed-compile`) does not populate intercept trend counters.
- Zero-value percentages in this panel indicate no intercept telemetry events in-window, not a compile failure state.

## 9) Final CFO Compile Verification

- Validation execution ID: `e118509c-3ae1-5989-b6da-7fc208eaaa76`
- Decision status: `recommended`
- Quality gates: no failures
- Freshness gate: `llm_freshness = CURRENT` (source: `payload.llm_audit_timestamp`)
- Replay/signing/manifest checks: PASS
- Decision pack artifact: `docs/release/evidence/2026-03-10-prod-baseline/decision-pack_e118509c-3ae1-5989-b6da-7fc208eaaa76.zip`

## 10) Release Package Hashes

- `diiac-v1.2.1-customer-release.zip`
  - SHA256: `4e7c6d6ee6ccc1df7d564a09331e119ee2f2a7e9d52280fdd811522223f464ee`
- `diiac-v1.2.1-evidence-pack.zip`
  - SHA256: `adf3c5706312c208bc9f3f5b567f8e4998b52a659ff3524eba2b1d871a552561`

