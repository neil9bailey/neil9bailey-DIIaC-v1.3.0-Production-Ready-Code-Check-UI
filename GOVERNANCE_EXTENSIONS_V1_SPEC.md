# DIIaC Governance Extensions v1 Spec

## Scope
This v1 spec defines concrete implementation contracts for:
1. Merkle root binding
2. Signed pack exports
3. Public verification endpoints
4. Admin settings for governance observability and auditor exports

---

## 1) Merkle Root Binding (v1)

### Objectives
- Replace flat "hash-of-hashes only" integrity with Merkle-tree verifiability.
- Support inclusion proofs for single artefacts without requiring whole-pack recomputation.

### Data Model Changes
Add to `governance_manifest.json`:
- `merkle` object:
  - `algorithm`: `sha256`
  - `leaf_canonicalization`: `sha256(name + ":" + hash)`
  - `leaf_count`: integer
  - `leaves`: ordered list of `{ name, hash, leaf_hash }`
  - `merkle_root`: hex string

Add to ledger records (`GOVERNED_EXECUTION`, `GOVERNED_MULTI_ROLE_COMPILE`):
- `merkle_root`
- `manifest_hash`

### Canonical Tree Rules
- Leaves sorted lexicographically by artefact filename.
- Odd node handling: duplicate last node at each level.
- Internal node hash: `sha256(left + right)`.
- Hash encoding: lowercase hex.

### API Additions
- `GET /executions/:execution_id/merkle`
  - Returns manifest merkle object.
- `GET /executions/:execution_id/merkle/proof/:artefact_name`
  - Returns inclusion proof: `leaf_hash`, `siblings[]`, `index`, `merkle_root`.

### Acceptance Criteria
- Same artefact set/content yields same `merkle_root` under strict deterministic mode.
- Inclusion proof verification for any artefact returns true with independent verifier.

---

## 2) Signed Pack Exports (v1)

### Objectives
- Provide authenticity and non-repudiation for exported decision packs.
- Allow third-party verification independent of DIIaC runtime.

### Signing Standard
- Algorithm: `Ed25519`.
- Signature mode: detached signature over ZIP bytes.
- Signing payload:
  - `sha256(zip_bytes)`
  - `execution_id`
  - `pack_hash`
  - `merkle_root`
  - `manifest_hash`

### Export Outputs
When calling export endpoint:
- `decision-pack_<execution_id>.zip`
- `decision-pack_<execution_id>.sig` (base64 detached signature)
- `decision-pack_<execution_id>.sigmeta.json` with:
  - `signature_alg`
  - `signing_key_id`
  - `signed_at`
  - `zip_sha256`
  - `execution_id`
  - `pack_hash`
  - `merkle_root`
  - `manifest_hash`

### Key Management (v1 baseline)
- Private key loaded from secure secret source (env/KMS wrapper).
- Public key registry file at `/workspace/contracts/keys/public_keys.json`.
- `signing_key_id` mandatory in signature metadata.

### API Additions
- `GET /decision-pack/:execution_id/export-signed`
  - Streams ZIP and writes/returns signature bundle metadata.

### Acceptance Criteria
- External verifier validates signature with published public key.
- Tampered ZIP or metadata fails verification.

---

## 3) Public Verification Endpoint (v1)

### Objectives
- Enable independent cryptographic verification by customers, auditors, regulators.

### Endpoint Set
- `POST /verify/pack`
  - Inputs: ZIP hash, signature, sigmeta, public key/key-id.
  - Outputs:
    - `signature_valid`
    - `hash_valid`
    - `manifest_consistent`
    - `overall_valid`
- `POST /verify/merkle-proof`
  - Inputs: `leaf_hash`, `siblings`, `index`, `merkle_root`.
  - Output: `proof_valid`
- `GET /verify/execution/:execution_id`
  - Returns verification summary derived from stored artefacts:
    - `pack_hash`
    - `merkle_root`
    - `ledger_record_hash`
    - `signature_present`
    - `status`

### Security and Rate Controls
- Verification endpoints are read-only.
- Apply request size limits and rate limiting.
- Redact internal-only fields from public responses.

### Acceptance Criteria
- Public verifier can validate signed pack and merkle proof without admin privileges.

---

## 4) Admin Settings: Observability + Auditor Export (v1)

### Objectives
- Give Admin role operational transparency for governance health.
- Provide auditor-friendly export bundle for evidence and logs.

### New Admin UI Area
Add `Admin Settings` page with tabs:
1. **System Health**
   - Service status (backend/frontend)
   - Last successful compile timestamp
   - Ledger record count + latest root
   - Recent failed executions count
2. **Runtime Logs**
   - Backend app logs (filtered by level/time)
   - Execution logs (per execution id)
   - Governance policy enforcement events
3. **Container / Platform Logs**
   - Surface container logs where accessible (backend/frontend)
   - Fallback guidance if runtime cannot access docker daemon
4. **Audit Export**
   - Generate downloadable audit package by date range/execution IDs

### Audit Export Bundle Contents
- `audit_manifest.json`
- Selected `decision-pack` artefacts
- Ledger slice (`ledger.jsonl` subset)
- Verification snapshots (`verify_execution` outputs)
- System and execution logs (redacted policy)
- Signature and merkle verification results

### API Additions
- `GET /admin/health`
- `GET /admin/logs?source=backend&level=...&from=...&to=...`
- `GET /admin/executions/:execution_id/logs`
- `POST /admin/audit-export`
  - Body: time range, execution IDs, include/exclude log classes
  - Returns: downloadable audit archive

### Access Control
- Admin-only by default.
- Optional `auditor` read/export role (future compatible).
- All admin/auditor access actions appended to ledger as `GOVERNANCE_AUDIT_ACCESS` records.

### Acceptance Criteria
- Admin can view health and logs without shell access.
- Auditor export produces self-contained evidence package and verification outputs.
- Access events are auditable and immutable via ledger append.

---

## Delivery Sequence (Recommended)
1. Merkle root + proof endpoints
2. Signed export + key registry
3. Public verification endpoints
4. Admin settings/log views + auditor export package

This order maximizes immediate assurance gains while keeping implementation risk controlled.
