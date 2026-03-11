# DIIaC Current Architecture Blueprint (v1.1.0 Updated)

## 1) Executive Snapshot

DIIaC (Decision Intelligence Infrastructure as Code) is implemented as a deterministic governance runtime that compiles role-based inputs into auditable decision artefacts, applies cryptographic sealing, and exposes public verification and admin operations.

Operating principle:

> Human/role input in → deterministic governed compile → cryptographically sealed artefacts + verifiable ledger output.

## 2) Runtime Topology

- **Core runtime:** Flask service (`app.py`) exposing governance, verification, trust, export, and admin endpoints.
- **Persistence:** SQLite (`runtime/diiac_runtime.db`) for role inputs, executions, backend logs, ledger logs, and audit exports.
- **Artefact storage:** local filesystem under `artifacts/`, `exports/`, and `audit_exports/`.
- **Contracts/config:** `contracts/business-profiles/*` and `contracts/keys/public_keys.json`.

## 3) Governance Pipeline (Operational)

1. Collect role inputs for `execution_context_id`.
2. Validate schema/profile constraints and R/P inputs.
3. Compute deterministic context hash.
4. Generate deterministic section draft and enforce required sections.
5. Generate deterministic scoring + recommendation.
6. Emit report artefacts + governance manifest.
7. Build Merkle leaf set/root for pack binding.
8. Sign export metadata and detached signature (Ed25519).
9. Append hash-linked ledger record.
10. Persist execution/log state to SQLite.

## 4) Security and Access Controls

- Optional admin auth mode with `ENFORCE_ADMIN_AUTH=true`.
- Admin auth methods:
  - API key (`x-role: admin` + `x-api-key`).
  - JWT Bearer HS256 (`Authorization: Bearer ...`) with `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`.
- Request payload size guard via `MAX_REQUEST_BYTES` (`MAX_CONTENT_LENGTH`).
- Route-level payload validation for compile and role ingestion.

## 5) Cryptographic and Verification Surfaces

- SHA-256 context hash, pack hash, manifest hash.
- Merkle root generation and proof verification.
- Key registry publication at `/verify/public-keys`.
- Pack verification uses signing key lookup by `signing_key_id` from key registry.
- Replay attestation endpoint (`/verify/replay`) emits `replay_certificate.json`.

## 6) Trust, Audit, and Operations

- Hash-linked ledger records and trust endpoint (`/trust/status`).
- Admin logs, execution logs, audit export bundle generation/download.
- DB operations:
  - `/admin/db/status`
  - `/admin/db/table/<table>`
  - `/admin/db/maintenance/compact`
- Startup state rehydration from SQLite into in-memory indexes.

## 7) Observability

- Request correlation via `X-Request-ID` (pass-through or generated).
- Response timing via `X-Response-Time-Ms`.
- Per-route aggregated metrics in `/admin/metrics`.

## 8) Governance Review APIs

- Execution trace map: `/executions/<id>/trace-map`
- Scoring view: `/executions/<id>/scoring`
- Deterministic execution diff: `/executions/<id>/diff/<other_id>`

## 9) Detailed Capability List (Current)

1. Multi-role input ingestion and context bundling.
2. Profile-driven schema policy checks.
3. Deterministic strict-mode execution IDs for replayability.
4. Deterministic section enforcement with placeholder insertion.
5. Deterministic scoring matrix + recommendation output.
6. Evidence trace mapping claim-to-source.
7. Pack artefact hashing and manifest creation.
8. Merkle root + proof generation/verification.
9. Ed25519 signature metadata and detached signature export.
10. Public key publication and key-id based signature verification.
11. Replay attestation with certificate emission.
12. Trust/ledger visibility APIs.
13. Admin logs, audit export, and execution log inspection.
14. SQLite persistence and startup rehydration.
15. Admin DB inspection and VACUUM maintenance.
16. Request correlation, latency headers, and route metrics.
17. Compatibility endpoints (`/govern/decision`, `/api/impact/policy`, `/decision-pack/<id>/export`).

## 10) Remaining Enhancements (Planned)

- Rate limiting and abuse controls.
- Offline verifier CLI for third-party validation.
- Data retention/archival policy automation.
- Expanded frontend parity for admin and governance controls.
