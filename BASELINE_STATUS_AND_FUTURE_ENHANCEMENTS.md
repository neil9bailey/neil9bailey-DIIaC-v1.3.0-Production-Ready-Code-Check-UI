# DIIaC Baseline Status and Future Enhancements

## Current Production-Ready Baseline (Implemented)

### Governance runtime
- Deterministic governed compile pipeline with profile/schema policy checks.
- Multi-role ingestion and compile surfaces:
  - `POST /api/human-input/role`
  - `POST /api/governed-compile`
  - `POST /govern/decision` (compat alias)
- Deterministic section enforcement and deterministic vendor scoring.

### Cryptographic and verification surfaces
- SHA-256 hash chain surfaces: context hash, pack hash, manifest hash.
- Merkle root binding and proof generation/verification.
- Ed25519 signing for signed export metadata and detached signature files.
- Public verification endpoints:
  - `GET /verify/execution/<id>`
  - `POST /verify/pack` (signing key lookup via key registry)
  - `POST /verify/merkle-proof`
  - `POST /verify/replay` (deterministic replay attestation + certificate emission)
  - `GET /verify/public-keys`

### Trust and administration
- Trust and health endpoints.
- Admin logs, execution logs, audit export generation and download.
- Signed/unsigned decision pack export endpoints.
- Deterministic diff endpoint:
  - `GET /executions/<id>/diff/<other_id>`

### Durability and operability enhancements
- SQLite-backed runtime persistence at `runtime/diiac_runtime.db`.
- Persisted tables for:
  - `role_inputs`
  - `executions`
  - `backend_logs`
  - `ledger_logs`
  - `audit_exports`
- Startup rehydration of in-memory maps from SQLite persisted state.
- Admin DB operations:
  - `GET /admin/db/status`
  - `GET /admin/db/table/<table_name>?limit=<n>`
  - `POST /admin/db/maintenance/compact`

### Security and robustness enhancements
- Optional admin-route protection via environment toggles:
  - `ENFORCE_ADMIN_AUTH=true`
  - `ADMIN_API_KEY=<secret>` (header `x-api-key`)
  - `JWT_SECRET=<secret>` with Bearer JWT (`HS256`) and issuer/audience controls (`JWT_ISSUER`, `JWT_AUDIENCE`)
- Role-scoped admin guard remains enforced with `x-role: admin`.
- Request payload size limit via `MAX_REQUEST_BYTES`.
- Additional payload validation for role ingest and governed compile fields.

### Observability enhancements
- Structured request correlation:
  - inbound `X-Request-ID` accepted or generated per request
  - `X-Request-ID` + `X-Response-Time-Ms` emitted on responses
- Request metrics aggregated per route and surfaced in:
  - `GET /admin/metrics`
- DB status includes basic key/profile integrity checks.

## Remaining Proposed Next Enhancements

1. **Rate limiting and abuse controls**
   - Add per-IP and per-key request throttling.
2. **Independent offline verifier tool**
   - CLI verification for decision-pack zip, sig, sigmeta, and merkle proofs.
3. **Data lifecycle controls**
   - Retention policies, compaction/archive jobs, and export cleanup tooling.
4. **Front-end hardening and parity**
   - Expand UI beyond current minimal baseline to expose role/schema/trace/DB admin controls.

## Recommended rollout sequence

1. Enable optional auth modes in non-prod and verify route compatibility.
2. Run deterministic replay/compile soak tests under realistic load.
3. Validate DB maintenance/backup policy and restore drill.
4. Promote with metrics and alerting in place.
