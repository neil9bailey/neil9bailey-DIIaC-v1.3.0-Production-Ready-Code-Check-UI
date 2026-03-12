# Offline Verifier Runbook (v1.3.0-ui)

This runbook validates exported decision packs in an offline or controlled environment.

## Inputs

- Exported decision pack archive
- Public key registry (`contracts/keys/public_keys.json`)
- Hash/signature metadata from pack manifest

## Verification Steps

1. Extract pack contents.
2. Validate manifest structure.
3. Recompute hashes for manifest-linked files.
4. Validate Merkle root and hash chain references.
5. Validate signature against configured key ID and public key.
6. Confirm replay verification succeeds.

## Expected Output

- Deterministic verification result (`pass`/`fail`)
- Failure reason list when verification does not pass
- Immutable verification log for audit storage

## Notes

- Production key material must remain in Key Vault; only public keys are used for offline verification.
- Any key mismatch or hash drift is a deployment/audit event and must be escalated.
