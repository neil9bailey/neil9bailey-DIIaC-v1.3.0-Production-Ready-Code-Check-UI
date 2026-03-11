# DIIaC Current Architecture Blueprint (v1.1.0 Baseline)

## Runtime topology
- Flask governance runtime (`app.py`) exposes deterministic compile, trust, verification, and admin APIs.
- Profile contracts are loaded from `contracts/business-profiles/*_profile_v1.json`.
- Public key registry is loaded from `contracts/keys/public_keys.json`.
- Runtime artifacts/exports/audit files are written to:
  - `artifacts/`
  - `exports/`
  - `audit_exports/`

## Governance compile pipeline
1. Collect role inputs via `POST /api/human-input/role`.
2. Execute governed compile via `POST /api/governed-compile`.
3. Persist decision-pack artifacts and governance manifest.
4. Append trust ledger record with hash chaining.
5. Expose verification surfaces for execution/pack/merkle/replay checks.

## Determinism and cryptographic controls
- Strict deterministic mode controlled by `STRICT_DETERMINISTIC_MODE=true`.
- Hash primitives use SHA-256 lower-hex.
- Merkle binding and proof APIs are operational.
- Signed exports use Ed25519 runtime signing key.

## Operational controls
- Admin auth is enforced by default in non-development environments for `/admin/*` using bearer token (`ADMIN_API_TOKEN`).
- Runtime readiness is exposed by `/health` and `/admin/health`.
- Structured runtime dependency failure taxonomy is returned as `runtime_dependency_failure` with endpoint-specific `error_code` values.
- Payload bounds are enforced on key write and verify endpoints.

## Intended operating model
- Baseline is suitable for controlled production-hardening validation.
- Remaining improvements focus on full UI E2E baselines and expanded operational rollout guidance.
