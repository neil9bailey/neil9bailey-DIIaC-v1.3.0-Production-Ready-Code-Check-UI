# DIIaC v1.1.0 Capabilities Matrix

## Sheet 1 Equivalent: Core Capabilities
| Capability | Category | Status | Evidence | Regulatory Relevance | Competitive Position |
|---|---|---:|---|---|---|
| Context hash | Cryptographic | Operational | execution artifacts | ISO 27001 A.8.24 | Enhanced |
| Pack hash | Cryptographic | Operational | execution_state | ISO 27001 A.8.24 | Enhanced |
| Manifest hash | Cryptographic | Operational | manifest + ledger | NIST SA-15 | Enhanced |
| Ledger chaining | Governance | Operational | ledger records | NIST AU-12 | Unique |
| Merkle root binding | Cryptographic | Operational | `/executions/:id/merkle` | EU AI Act Art.53 | Unique |
| Merkle proof generation | Verification | Operational | `/merkle/proof/:artefact` | EU AI Act Art.53 | Unique |
| Signed export (Ed25519) | Cryptographic | Operational | `signed_export.sigmeta.json` | NIST AU-10 | Unique |
| Verify execution endpoint | Verification | Operational | `/verify/execution/:id` | EU AI Act Art.53 | Unique |
| Verify pack endpoint | Verification | Operational | `/verify/pack` | NIST AU-10 | Enhanced |
| Verify public keys endpoint | Verification | Operational | `/verify/public-keys` | ISO/NIST evidence | Enhanced |
| Admin health | Observability | Operational | `/admin/health` | ISO logging | Standard |
| Admin log access | Observability | Operational | `/admin/logs` | ISO logging | Enhanced |
| Audit export generation | Governance | Operational | `/admin/audit-export` | NIST AU-12 | Enhanced |
| Multi-role compile | Governance | Operational | `/api/governed-compile` | risk governance | Enhanced |
| Tier enforcement R/P | Governance | Operational | reports + logs | NIST AI RMF | Unique |
| Evidence trace map | Governance | Operational | `evidence_trace_map.json` | auditability | Enhanced |
| Deterministic strict mode | Governance | Operational | deterministic tests | validation | Enhanced |
| Vendor scoring matrix | Governance | Operational | scoring artifact | procurement | Standard |

## Sheet 2 Equivalent: v1.1 Feature Detail
- Merkle roots/proofs: implemented in backend routes and manifests.
- Signed exports: auto-generated at execution time when signing enabled.
- Public verification: pack/execution/public-key routes active.
- Admin console support: health, logs, execution verification, audit export.

## Sheet 3 Equivalent: Regulatory Mapping Examples
- EU AI Act Article 53 → `/verify/execution`, Merkle proofs, audit exports
- ISO 27001 A.8.24 → SHA-256 + Ed25519 signing workflow
- NIST AU-10 → signature validation and key disclosure path
- NIST AU-12 → ledger + audit export generation and retrieval
