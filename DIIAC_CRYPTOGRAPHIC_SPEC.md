# DIIaC v1.1.0 Cryptographic Specification

## Hashing Standard
- Algorithm: SHA-256
- Encoding: lowercase hex
- Deterministic hash derivation for artifact and chain operations

## Integrity Chain Elements
- Context hash (input-linked)
- Pack hash (artifact package fingerprint)
- Manifest hash
- Merkle root (artifact aggregation proof root)
- Ledger record hash chain

## Merkle Tree Rules
- Leaves sorted lexicographically by artifact filename
- Leaf hash canonicalization: `sha256(name:hash)`
- Odd node duplication rule when building parent layers
- Parent hash: `sha256(left + right)`

## Inclusion Proof Shape
```json
{
  "artefact_name": "board_report.json",
  "leaf_hash": "...",
  "index": 0,
  "siblings": ["..."],
  "merkle_root": "..."
}
```

## Digital Signature Workflow
- Algorithm: Ed25519
- Payload includes execution id, pack hash, merkle root, manifest hash, signed timestamp
- Signature and metadata emitted into artifacts:
  - `signed_export.sig`
  - `signed_export.sigmeta.json`

## Verification Paths
- `POST /verify/pack` validates signature and payload consistency
- `POST /verify/merkle-proof` validates inclusion proof chain
- `GET /verify/public-keys` exposes verification key set

## Key Management
- Runtime key from `SIGNING_PRIVATE_KEY_PEM` if configured
- Fallback ephemeral key for local/dev execution
- `SIGNING_ENABLED` runtime switch controls signing behavior
