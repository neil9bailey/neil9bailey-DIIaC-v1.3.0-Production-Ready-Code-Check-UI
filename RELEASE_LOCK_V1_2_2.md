# DIIaC v1.2.2 Release Lock Record

## Status: LOCKED — Production Baseline

**Tag:** `v1.2.2`
**Branch at lock:** `claude/continue-session-WvsS0`
**Tests:** 30/30 passing
**Git tree:** clean

---

## What This Release Contains

### v1.2.0 — Core Governed Compile + UI
- Deterministic governed multi-role compile
- Merkle binding, pack hashing, manifest integrity
- Governance manifest, evidence trace, vendor scoring
- Board report generation with structured sections
- Replay verification and deterministic execution IDs
- Audit export with ledger slice
- React Frontend + Backend-UI-Bridge + Governance Runtime (three-service stack)
- Entra ID authentication (OIDC + group/role mapping)
- Admin API with auth enforcement in production

### v1.2.0-ledger-anchored — Ledger Anchoring
- Append-only trust ledger with SHA-256 chain
- `LEDGER_FREEZE` flag for demo/audit environments
- Ledger records in `/trust/status` and admin endpoints
- `ledger_record_hash` on every execution

### v1.2.1 — Signing Provider Abstraction
- `SigningProvider` abstraction with `LocalEdDSASigner` (Ed25519) and `AzureKeyVaultSigner` (ES256)
- Azure Key Vault integration with customer-managed vault model
- `SIGNING_PROVIDER`, `KEYVAULT_*`, `KEYVAULT_TENANT_ID` env vars
- `SIGNING_PRIVATE_KEY_PEM` for persistent Ed25519 key injection
- `verify_signature` on all providers

### v1.2.2 — Algorithm-Aware Signature Verification ✅
- `_verify_signature_dispatch` — reads `signature_alg` from `signed_export.sigmeta.json` as canonical source of truth
- Ed25519 → `Ed25519PublicKey.from_public_bytes().verify()`
- ES256 → `load_der_public_key()` + `ECDSA(SHA256()).verify()`
- Algorithm checked before key lookup (clear error ordering)
- Error taxonomy: `missing_signature_alg`, `missing_signature`, `unsupported_signature_alg`, `public_key_not_found`, `signature_verification_failed`
- `/verify/pack` uses dispatcher — additive response fields: `signature_alg`, `signing_key_id`, `verification_provider`
- `/verify/execution` — additive fields: `signature_alg`, `signing_key_id`
- `public_keys.json` init: always upserts current key (supports mixed Ed25519 + ES256 ledgers)
- Tests: `test_verify_pack_ed25519_still_passes`, `test_verify_pack_es256_passes_with_akv_signature`, `test_verify_pack_rejects_unsupported_signature_alg`

---

## Mandatory Validation Gate (Executed at Lock)

```
30/30 tests passing
Git tree: clean — nothing to commit
All cryptographic paths verified (Ed25519 regression + ES256 new path + unsupported alg negative)
```

---

## Known Constraints (Documented, Not Blockers)

| Constraint | Impact | Mitigation |
|---|---|---|
| In-memory execution state | Lost on restart | Artifacts persist on Docker volumes; documented in DEPLOYMENT_GUIDE.md |
| Flask dev server in base compose | Single-threaded | Deployment package uses gunicorn; see DIIaC-V1.2.0-Production-Ready-Deployment |
| Ephemeral Ed25519 key by default | Can't verify cross-restart without config | `SIGNING_PRIVATE_KEY_PEM` or AKV mandated in deployment runbook |

---

## Delivery Packages

| Package | Repo | Purpose |
|---|---|---|
| Development + test baseline | `DIIaC-v1.2.0-Production-Ready-Code-Check` | This repo — ongoing test and reference |
| Customer deployment package | `DIIaC-V1.2.0-Production-Ready-Deployment` | Cleaned, production docker-compose, gunicorn, .env.example, DEPLOYMENT_GUIDE.md, LICENSE |
| v1.3.0 headless development | `DIIaC-v1.3.0c-Production-Ready-Codebase` | LLM-native UI, persistence layer, multi-tenant, SaaS model |

---

## Tag Workflow

```bash
git tag -a v1.2.2 -m "DIIaC v1.2.2 — algorithm-aware signature verification, production baseline"
git push origin v1.2.2
```

## v1.3.0 Entry Conditions
Branching from this commit. Key changes required before v1.3.0 ships:
1. Real persistence layer (replace in-memory dicts — `DATABASE_URL` already stubbed)
2. LLM ingestion endpoint (`LLM_INGESTION_ENABLED` flag already wired)
3. Multi-tenant execution context isolation
4. SaaS deployment package (Helm / Azure Container Apps)
5. Frontend gated to dashboard-only; primary UX via LLM interface
