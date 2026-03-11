# Baseline Status and Future Enhancements

## Completed in current baseline
1. Deterministic governed compile flow with role-driven inputs.
2. Cryptographic verification surfaces:
   - execution verification
   - pack verification
   - merkle proof verification
   - replay attestation verification
   - public key exposure
3. Trust and audit operations:
   - ledger growth/trust status
   - admin logs/health/metrics
   - audit export generation + download
4. Security/runtime hardening:
   - admin auth default enforcement in non-dev
   - payload bounds on critical write endpoints
   - runtime readiness checks
   - structured runtime dependency error taxonomy
5. Verification hardening:
   - offline verifier runbook
   - tamper tests for pack/merkle mismatches

## Remaining hardening priorities
1. UI end-to-end confidence
   - runtime API E2E smoke script implemented (`scripts_e2e_runtime_smoke.py`) for role input/compile/trust/admin/logs/audit flows
   - remaining: browser/UI-level scripted E2E and baseline screenshots
2. Operational rollout maturity
   - production-mode readiness validation script implemented (`scripts_production_readiness_check.py`)
   - richer threshold/alert recommendations and incident triage guidance implemented in `/admin/metrics` (MTR-001 through MTR-005, triage map, 5 threshold fields)
   - deployment validation runbook implemented (`DEPLOYMENT_VALIDATION_RUNBOOK.md`)
3. Documentation alignment hygiene
   - keep architecture/alignment docs synchronized with implemented behavior and tests each release slice

## Release criteria for baseline validation
- All automated tests green (`pytest -q`).
- Admin route auth deny/allow matrix remains passing.
- Deterministic replay and verification tamper checks remain passing.
- No unresolved drift between code behavior and published docs.
