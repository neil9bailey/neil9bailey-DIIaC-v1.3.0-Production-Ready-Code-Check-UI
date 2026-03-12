# Offline Verifier Runbook (v1.3.0-ui)

This runbook validates exported decision packs in an offline or controlled environment.

## Inputs

- Exported decision pack archive (or extracted pack directory)
- `signed_export.sigmeta.json` and `verification_manifest.json` from the pack
- Optional public key registry (`contracts/keys/public_keys.json`) if `public_key_b64` is not embedded in sigmeta

## Verification Steps

1. Extract pack contents.
2. Validate manifest structure.
3. Recompute hashes for manifest-linked files.
4. Validate Merkle root and hash chain references.
5. Validate signature against canonical `signature_payload` using Ed25519.
6. Confirm payload alignment (`execution_id`, `pack_hash`, `manifest_hash`, `merkle_root`).
7. Confirm replay verification succeeds.

## Automated Command

Run:

`node scripts/verify_decision_pack.js <path-to-extracted-pack> [path-to-public_keys.json]`

Output is a JSON pass/fail report with per-check status.

## Expected Output

- Deterministic verification result (`pass`/`fail`)
- Failure reason list when verification does not pass
- Immutable verification log for audit storage

## Notes

- Production key material must remain in Key Vault; only public keys are used for offline verification.
- Any key mismatch or hash drift is a deployment/audit event and must be escalated.
- Policy pack `PASS/FAIL` values are internal control-signal assessments, not legal compliance determinations.
