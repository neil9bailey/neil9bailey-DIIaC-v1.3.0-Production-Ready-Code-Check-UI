# Cryptographic Specification (v1.3.0-ui)

## Objectives

- Deterministic output integrity
- Verifiable chain of custody for governance artifacts
- Replay-safe verification for audit

## Core Primitives

- Hashing: SHA-256
- Signing: Ed25519
- Canonical serialization: stable JSON ordering for deterministic hashing

## Integrity Structures

1. File/content hashes in manifests
2. Merkle tree roots over selected execution artifacts
3. Ledger hash chain for append-only traceability

## Key Management

- Production private key material is injected from Key Vault.
- Public keys are maintained in `contracts/keys/public_keys.json`.
- Ephemeral keys are local/dev only and not acceptable for production trust readiness.

## Verification Expectations

A verification pass requires:

- Hashes match recomputed values.
- Signature verifies with expected key ID.
- Ledger chain integrity is intact.
- Merkle proof/root consistency holds.
