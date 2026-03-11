# DIIaC v1.1.0 Capabilities Matrix (Updated)

## Core Capabilities

| Capability | Category | Status | Operational Evidence | Notes |
|---|---|---|---|---|
| Multi-role input ingestion | Governance | Operational | `POST /api/human-input/role` | Structured role bundle collection |
| Profile registry and loading | Governance | Operational | `GET /api/business-profiles` | Profile-hash governed configuration |
| Governed compile (primary + compat) | Governance | Operational | `POST /api/governed-compile`, `POST /govern/decision` | Blueprint compatibility preserved |
| Compile payload validation | Security | Operational | 400 `missing_fields` / `invalid_field` | Required field and level validation |
| Role payload validation | Security | Operational | 400 `missing_fields` / `invalid_field` | Role + array contract checks |
| Request payload size limits | Security | Operational | `MAX_REQUEST_BYTES` → Flask `MAX_CONTENT_LENGTH` | Basic abuse guard |
| Deterministic strict execution ID | Governance | Operational | strict mode replay-stable execution IDs | Enabled by strict deterministic mode |
| Context hash | Cryptographic | Operational | compile response + execution state | SHA-256 |
| Pack hash | Cryptographic | Operational | compile response + verify endpoint | SHA-256 |
| Manifest hash | Cryptographic | Operational | verify execution + manifest artifact | SHA-256 |
| Ledger chaining | Governance | Operational | `/trust/status`, `/admin/logs?source=ledger` | Hash-linked record chain |
| Merkle root binding | Cryptographic | Operational | `/executions/<id>/merkle` | Canonical leaf generation |
| Merkle proof generation | Verification | Operational | `/executions/<id>/merkle/proof/<artefact_name>` | Per-artefact proof |
| Merkle proof verification | Verification | Operational | `POST /verify/merkle-proof` | Deterministic verifier |
| Signed export (Ed25519) | Cryptographic | Operational | `/decision-pack/<id>/export-signed` + `signed_export.sigmeta.json` | Detached signature + metadata |
| Verify execution endpoint | Verification | Operational | `/verify/execution/<id>` | Ledger and pack status checks |
| Verify pack endpoint | Verification | Operational | `/verify/pack` | Signature/hash/manifest consistency |
| Key-id based signature verification | Verification | Operational | `/verify/pack` resolves key by `signing_key_id` | Uses public key registry |
| Verify public keys endpoint | Verification | Operational | `/verify/public-keys` | Key publication surface |
| Replay attestation endpoint | Verification | Operational | `POST /verify/replay` + `replay_certificate.json` | Deterministic replay evidence |
| Trust endpoint | Governance | Operational | `/trust/status` | Ledger health surface |
| Admin health/logs | Operations | Operational | `/admin/health`, `/admin/logs` | Operational introspection |
| Admin route auth (optional) | Security | Operational | `ENFORCE_ADMIN_AUTH` + API key/JWT + `x-role: admin` | Supports API key or HS256 JWT |
| Audit export generation | Governance | Operational | `POST /admin/audit-export`, download endpoint | Portable audit bundle |
| SQLite runtime persistence | Durability | Operational | `runtime/diiac_runtime.db` | Execution/log durability |
| Startup DB rehydration | Durability | Operational | state restored on app startup | In-memory map reconstruction |
| DB admin status/table/compact | Operations | Operational | `/admin/db/status`, `/admin/db/table/<table>`, `/admin/db/maintenance/compact` | DB governance controls |
| Per-request correlation ID | Observability | Operational | `X-Request-ID` request/response headers | Traceability |
| Response latency header | Observability | Operational | `X-Response-Time-Ms` | Basic latency telemetry |
| Per-route aggregated metrics | Observability | Operational | `/admin/metrics` route statistics | Request/error counters |
| Governance diff endpoint | Governance | Operational | `/executions/<id>/diff/<other_id>` | Hash + section-level comparison |
| Evidence trace map | Governance | Operational | `evidence_trace_map.json`, `/executions/<id>/trace-map` | Claim/source traceability |
| Deterministic vendor scoring matrix | Governance | Operational | `/executions/<id>/scoring` + artifact | Reproducible decision scoring |

## Regulatory Mapping Examples

- **EU AI Act Article 53** → execution verification, Merkle proofs, audit exports.
- **ISO 27001 A.8.24** → hashing/signing integrity controls.
- **NIST AU-10 / AU-12** → signature validation, ledger, and auditable export paths.
