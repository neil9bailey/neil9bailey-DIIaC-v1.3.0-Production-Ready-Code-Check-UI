# DIIaC Current Architecture Blueprint (v1.2.1)

> Detailed target-state blueprint: `docs/architecture/DIIAC_GOVERNANCE_LAYER_BLUEPRINT_v1.2.1.md`

## Runtime topology
- Flask governance runtime (`app.py`) exposes deterministic compile, trust, verification, and admin APIs.
- Profile contracts are loaded from `contracts/business-profiles/*_profile_v1.json`.
- Policy packs are loaded from `contracts/policy-packs/*_v1.json`.
- Public key registry is loaded from `contracts/keys/public_keys.json`.
- Runtime artifacts/exports/audit files are written to:
  - `artifacts/`
  - `exports/`
  - `audit_exports/`

## Governance compile pipeline
1. Collect role inputs via `POST /api/human-input/role`.
2. Execute governed compile via `POST /api/governed-compile`.
3. Freeze deterministic input snapshot and hash.
4. Evaluate profile controls + policy-pack controls + evidence gates.
5. Persist decision-pack artifacts, replay certificate, and governance manifest.
6. Append trust ledger record with hash chaining.
7. Expose verification surfaces for execution/pack/merkle/replay checks.

## Determinism and cryptographic controls
- Strict deterministic mode controlled by `STRICT_DETERMINISTIC_MODE=true`.
- Hash primitives use SHA-256 lower-hex.
- Merkle binding and proof APIs are operational.
- Signed exports use Ed25519 runtime signing key.
- Replay certificate emitted for deterministic executions.
- Deterministic input freeze hash included in execution artifacts.

## Governance gates
- Evidence quality gates:
  - minimum strong evidence refs
  - minimum claim coverage
  - optional fresh LLM audit timestamp requirement
- Decision statuses:
  - `recommended`
  - `needs_more_evidence`
  - `not_recommended`
- Policy-pack control failures can be enforced to block recommendation.

## Operational controls
- Admin auth is enforced by default in non-development environments for `/admin/*` using bearer token (`ADMIN_API_TOKEN`).
- Runtime readiness is exposed by `/health` and `/admin/health`.
- `policy_packs_loaded` is part of readiness.
- Structured runtime dependency failure taxonomy is returned as `runtime_dependency_failure` with endpoint-specific `error_code` values.
- Payload bounds are enforced on key write and verify endpoints.
- Role input idempotency prevents duplicate role submission contamination.

## Intended operating model
- DIIaC operates as a provider-agnostic governance layer wrapping LLM workflows.
- LLM providers remain interchangeable integration targets; governance and determinism remain constant.
- Auditor-ready assurance is built from deterministic input freeze, policy-pack compliance, cryptographic evidence chain, and replay verification.
