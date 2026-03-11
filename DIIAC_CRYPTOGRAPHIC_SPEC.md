# DIIaC v1.1.0 Cryptographic Specification

- Hashing: SHA-256 lowercase hex.
- Chain elements: context hash, pack hash, manifest hash, merkle root, ledger record hash chain.
- Merkle rules:
  - leaves sorted lexicographically by artifact filename
  - leaf hash = `sha256(name:hash)`
  - odd duplication at each layer
  - parent hash = `sha256(left + right)`
- Signature workflow:
  - Ed25519
  - runtime key via `SIGNING_PRIVATE_KEY_PEM` or ephemeral fallback
  - key id via `SIGNING_KEY_ID`
  - public keys from `/verify/public-keys` and `contracts/keys/public_keys.json`
