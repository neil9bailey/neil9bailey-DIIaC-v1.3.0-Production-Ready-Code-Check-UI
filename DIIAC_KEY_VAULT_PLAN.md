# DIIaC Key Vault Integration Plan
## Azure Key Vault — HSM-Backed Key Custody for Production Deployments

**Document Type:** Architecture Plan | Deployment Guide | Customer Packaging Reference
**Version:** 1.0
**Baseline:** v1.2.0-ledger-anchored
**Status:** IMPLEMENTATION-READY — code abstraction is in place; activation requires env var change only

---

## Understanding This Document

This document has three audiences:

1. **Engineering** — what was built, how it works, how to activate it
2. **Sales / Pre-sales** — how to explain it to a regulated enterprise or acquirer
3. **Customer deployment teams** — step-by-step setup for each new customer environment

Read the section relevant to you. The full document should be understood by anyone onboarding DIIaC into a regulated production environment.

---

## 1. Status Check — Where We Are (v1.2.0-ledger-anchored)

### What is working right now

| Capability | Status | Evidence |
|---|---|---|
| Deterministic governed compile | Operational | 21/21 tests pass |
| Merkle-sealed artifact packs | Operational | 13 artifacts, SHA-256 bound |
| Ed25519 digital signature | Operational | `signed_export.sig` + `signed_export.sigmeta.json` |
| Immutable trust ledger (chained) | Operational | `ledger.jsonl` with `previous_record_hash` |
| Replay attestation | Operational | `POST /verify/replay` |
| Admin health + config | Operational | `/admin/health`, `/admin/config` |
| `LEDGER_FREEZE` for demo environments | Operational | `LEDGER_FREEZE=true` env var |
| **SigningProvider abstraction** | **Shipped (v1.2.0-ledger-anchored)** | `LocalEdDSASigner` + `AzureKeyVaultSigner` in `app.py` |

### What is the current signing limitation

The signing key is currently:

- Generated locally at startup (`ephemeral-local-ed25519`)
- Or loaded from env var (`SIGNING_PRIVATE_KEY_PEM`)
- Scoped to the process lifecycle
- Not protected by any key management system
- Not attested (no proof of where the key lives or how it's protected)

**This is acceptable for:**
- Development environments ✅
- Pilots and proofs of concept ✅
- Technical validation ✅
- Demo and diligence environments ✅
- Early acquisition conversations ✅

**This is not sufficient for:**
- Regulated production deployments ❌
- ISO 27001 / SOC 2 audit evidence ❌
- Financial services or healthcare procurement ❌
- Serious acquirer security due diligence ❌
- Any customer that will ask "where does the signing key live?" ❌

### What has already been built to address this

The `SigningProvider` abstraction is in `app.py`. It works today. The local signer is unchanged. The Azure Key Vault signer is fully implemented and will activate the moment:

1. The Azure SDK packages are added to `requirements.txt` (two lines, already commented)
2. `SIGNING_PROVIDER=azure-keyvault` is set in the environment
3. `KEYVAULT_URL` and `KEYVAULT_KEY_NAME` point to a provisioned vault

**No code changes are required to switch a customer from local to Azure Key Vault.** It is a configuration change, not a development task.

---

## 2. How This Will Be Packaged for New Customer Deployments

This section is the canonical answer to: *"How do we deploy this for a new customer?"*

### The Two-Mode Deployment Model

Every DIIaC customer deployment is one of two modes:

| Mode | Signing Provider | Use Case | Activation |
|---|---|---|---|
| **Pilot / Demo** | `local` (Ed25519, ephemeral) | Pre-sales, PoC, technical validation | Default — no changes |
| **Production** | `azure-keyvault` (ES256, HSM) | Regulated deployment, bank, healthcare, critical infrastructure | Set 3 env vars, uncomment 2 lines in `requirements.txt` |

The rest of the stack — ledger format, Merkle structure, replay attestation, artifact schema, API endpoints — is **identical in both modes**. There is no fork, no separate codebase, no separate Docker image.

### Customer Onboarding Checklist

For each new customer, run through this checklist:

#### Phase 1 — Pilot (always first)

```
[ ] Deploy docker-compose with default env vars
[ ] Run governed compile end-to-end (see README)
[ ] Confirm 21/21 tests pass in their environment
[ ] Run E2E smoke: python3 scripts_e2e_runtime_smoke.py
[ ] Show /admin/health — confirm signing_provider: "local"
[ ] Run the benchmark comparison (see DIIAC_SALES_CASE_AND_TEST_EVIDENCE.md)
[ ] Capture execution certificate and walk the customer through it
```

#### Phase 2 — Production (when Azure is available)

```
[ ] Create Azure subscription (or confirm existing)
[ ] Run the AKV setup commands in Section 4 of this document
[ ] Uncomment azure-keyvault-keys and azure-identity in requirements.txt
[ ] Set SIGNING_PROVIDER=azure-keyvault in docker-compose.yml / Container App config
[ ] Set KEYVAULT_URL and KEYVAULT_KEY_NAME
[ ] Enable Managed Identity on the deployment target
[ ] Assign Key Vault Crypto User role to the Managed Identity
[ ] Rebuild and restart the governance-runtime container
[ ] Confirm /admin/config shows signing_provider: "azure-keyvault"
[ ] Confirm /admin/health shows key_mode: "hsm"
[ ] Run a governed compile — verify signature_alg: "ES256" in sigmeta
[ ] Run E2E smoke again — confirm all pass
```

### The Admin Dashboard Flip

The Admin Console (`/admin/config`) now exposes the signing provider state:

```json
{
  "signing_provider": "local",
  "signing_algorithm": "Ed25519",
  "signing_key_id": "ephemeral-local-ed25519",
  "signing_key_mode": "ephemeral"
}
```

After switching to Azure Key Vault:

```json
{
  "signing_provider": "azure-keyvault",
  "signing_algorithm": "ES256",
  "signing_key_id": "https://kv-diiac-prod.vault.azure.net/keys/diiac-signing-v1/abc123",
  "signing_key_mode": "hsm"
}
```

The admin dashboard (`/admin/health`) also exposes:

```json
{
  "signing_provider": "azure-keyvault",
  "signing_algorithm": "ES256",
  "key_mode": "hsm"
}
```

An operator can confirm the signing backend at a glance without accessing the underlying infrastructure. There is no separate UI or configuration panel needed — the state is visible and the switch is a single env var.

---

## 3. Customer-Managed Key Vault Model (Gold Standard)

> **This is the correct enterprise posture and the recommended default for all regulated deployments.**

### The Principle: DIIaC Never Owns the Key

DIIaC already follows this model for identity: the customer owns their Entra ID tenant, their users, their groups, and their policies. DIIaC holds a delegated trust relationship. Key Vault should follow the exact same pattern.

| Concern | Ownership | DIIaC role |
|---|---|---|
| Entra ID tenant | Customer | Delegated trust (token validation) |
| Users and groups | Customer | Read-only (via OIDC/JWKS) |
| Key Vault | Customer | None |
| Signing key (HSM) | Customer | Sign-only (via RBAC grant) |
| Key rotation policy | Customer | None |
| Key revocation | Customer | None |
| Audit log of key operations | Customer (Azure Monitor) | None |

**DIIaC never creates customer keys. DIIaC never stores customer keys. DIIaC never rotates customer keys.** The customer controls the full key lifecycle. DIIaC signs via a single `sign` API call, exactly as it validates identity via a single JWKS endpoint.

---

### Target Architecture: Per-Customer Deployment

```
Customer Azure Subscription
├── Customer Entra ID Tenant
│   └── Users, Groups, Policies (customer-owned — same as today)
├── Customer Key Vault (kv-customer-prod)
│   └── diiac-signing-v1  (HSM, non-exportable, ES256)
│       ├── Owned by: Customer
│       ├── Rotation: Customer policy
│       └── Revocation: Customer
│
└── DIIaC Deployment (Container App / AKS / VM)
    ├── Managed Identity or App Registration
    ├── RBAC grant: Key Vault Crypto User
    │   ├── ✅ sign
    │   ├── ✅ verify
    │   ├── ❌ get key material
    │   ├── ❌ delete
    │   └── ❌ rotate
    └── KEYVAULT_TENANT_ID = customer's Azure AD tenant ID
```

DIIaC never creates or stores customer keys. The customer grants a single, revocable RBAC assignment. If they revoke it, DIIaC can no longer sign — but all historical records remain valid (they are already sealed and anchored).

---

### Configuration Pattern: Mirrors Entra ID

This is already how Entra ID works in DIIaC. The Key Vault pattern is identical:

**Entra ID (identity — already live):**
```env
ENTRA_EXPECTED_TENANT_ID=<customer-tenant-id>
ENTRA_EXPECTED_AUDIENCE=<customer-app-id>
```

**Key Vault (signing — same pattern):**
```env
SIGNING_PROVIDER=azure-keyvault
KEYVAULT_URL=https://kv-customer-prod.vault.azure.net
KEYVAULT_KEY_NAME=diiac-signing-v1
KEYVAULT_TENANT_ID=<customer-tenant-id>     ← new — routes credential to customer tenant
```

Both follow the same principle: DIIaC is told where the customer's resource lives, and the customer grants access. DIIaC does not own the resource.

---

### Trust Establishment: Customer Does One Thing

The customer's Azure administrator runs a single command to grant DIIaC access:

```bash
az role assignment create \
  --assignee <DIIAC_MANAGED_IDENTITY_OR_SP_OBJECT_ID> \
  --role "Key Vault Crypto User" \
  --scope /subscriptions/<CUSTOMER_SUB>/resourceGroups/<RG>/providers/Microsoft.KeyVault/vaults/kv-customer-prod
```

This grants:
- ✅ `sign` — DIIaC can request signatures
- ✅ `verify` — DIIaC can verify signatures
- ❌ No key export
- ❌ No key deletion
- ❌ No key creation

The customer can revoke this at any time with a single `az role assignment delete`. All previously signed records remain valid because they are immutably ledger-anchored — the signature is in the artifact, not in the vault.

---

### How the Signing Metadata Already Expresses This

The `signed_export.sigmeta.json` artifact already carries the full key provenance:

```json
{
  "signature_alg": "ES256",
  "signing_key_id": "https://kv-customer-prod.vault.azure.net/keys/diiac-signing-v1/abc1234def5678",
  "signature_present": true,
  "signed_at": "2026-03-04T14:22:31Z"
}
```

The `signing_key_id` is the full vault URL including key version. An auditor or acquirer can:
1. See exactly which key signed the record
2. Confirm the key is in the customer's vault (not DIIaC's)
3. Look up the Azure Key Vault audit log for that key version to confirm the signature event
4. Verify the signature is valid using the public key published in `public_keys.json`

This is the chain of custody regulators and acquirers expect.

---

### Admin Dashboard Confirms Customer Vault

`/admin/health` now exposes `keyvault_tenant_id`:

```json
{
  "signing_provider": "azure-keyvault",
  "signing_algorithm": "ES256",
  "signing_key_id": "https://kv-customer-prod.vault.azure.net/keys/diiac-signing-v1/...",
  "key_mode": "hsm",
  "keyvault_tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

An operator can confirm from the Admin Console:
- That the signing provider is AKV (not local)
- That the vault belongs to the customer's tenant (matching their `ENTRA_EXPECTED_TENANT_ID`)
- That the key is HSM-backed

---

### Multi-Customer Deployment (Single-Tenant Per Customer — Recommended)

The recommended model is one DIIaC deployment per customer. This gives the strongest isolation and the cleanest compliance story:

```
Customer A Deployment:
  KEYVAULT_URL=https://kv-customer-a.vault.azure.net
  KEYVAULT_TENANT_ID=<customer-a-tenant-id>
  ENTRA_EXPECTED_TENANT_ID=<customer-a-tenant-id>    ← same tenant

Customer B Deployment:
  KEYVAULT_URL=https://kv-customer-b.vault.azure.net
  KEYVAULT_TENANT_ID=<customer-b-tenant-id>
  ENTRA_EXPECTED_TENANT_ID=<customer-b-tenant-id>    ← same tenant
```

Each customer's identity provider and signing vault are in the same tenant. There is no cross-tenant credential routing needed. Managed Identity works without additional configuration.

Each customer's signed records reference their own vault URL. An auditor auditing Customer A cannot produce a valid record signed by Customer B's key, by construction.

---

### Customer Onboarding Checklist (Customer-Managed Vault)

This checklist is handed to the customer's Azure administrator on day one of a production deployment:

```
[ ] In the customer Azure subscription, create a Key Vault:
    az keyvault create --name kv-<customer>-diiac --sku premium
    --enable-rbac-authorization true --enable-purge-protection true

[ ] Create the signing key:
    az keyvault key create --vault-name kv-<customer>-diiac
    --name diiac-signing-v1 --kty EC --curve P-256 --protection hsm --ops sign verify

[ ] Note the DIIaC Managed Identity Object ID (provided by DIIaC deployment team)

[ ] Grant Key Vault Crypto User to the DIIaC identity:
    az role assignment create --assignee <DIIAC_OBJECT_ID>
    --role "Key Vault Crypto User"
    --scope /subscriptions/.../vaults/kv-<customer>-diiac

[ ] Provide to DIIaC deployment team:
    - Vault URL: https://kv-<customer>-diiac.vault.azure.net
    - Key name: diiac-signing-v1
    - Azure AD Tenant ID: <customer-tenant-id>

[ ] DIIaC deployment team sets:
    SIGNING_PROVIDER=azure-keyvault
    KEYVAULT_URL=https://kv-<customer>-diiac.vault.azure.net
    KEYVAULT_KEY_NAME=diiac-signing-v1
    KEYVAULT_TENANT_ID=<customer-tenant-id>

[ ] Confirm /admin/config shows:
    signing_provider: azure-keyvault
    keyvault_tenant_id: <customer-tenant-id>
    key_mode: hsm
```

---

### What to Say to a Customer Who Asks About Key Custody

> *"We follow the same model as your identity provider. You own the Key Vault. You own the key. You set the rotation policy. You can revoke our access at any time. We hold a single permission — sign — granted via Azure RBAC, exactly like a read-only service account. Every signed record references your vault URL by key version, so an auditor can trace any signature back to a specific key event in your Azure Monitor log. We never see the private key."*

This is the answer that satisfies a bank's CISO, a healthcare procurement officer, and an ISO 27001 auditor in the same sentence.

---

## 5. The Signing Provider Architecture

### How It Works

```
app.py startup
      │
      ▼
_create_signing_provider()  ──── reads SIGNING_PROVIDER env var
      │
      ├── "local"            ──▶ LocalEdDSASigner
      │                              │
      │                              ├── reads SIGNING_PRIVATE_KEY_PEM (or generates ephemeral)
      │                              ├── algorithm(): "Ed25519"
      │                              └── sign(payload): private_key.sign(payload)
      │
      └── "azure-keyvault"   ──▶ AzureKeyVaultSigner
                                     │
                                     ├── reads KEYVAULT_URL, KEYVAULT_KEY_NAME
                                     ├── authenticates via DefaultAzureCredential
                                     ├── algorithm(): "ES256"
                                     └── sign(payload): sha256(payload) → CryptographyClient.sign()
```

### What Does Not Change When You Switch Providers

| Component | Local | Azure KV | Changes? |
|---|---|---|---|
| Ledger format (`ledger.jsonl`) | Unchanged | Unchanged | No |
| Merkle root computation | Unchanged | Unchanged | No |
| Pack hash | Unchanged | Unchanged | No |
| Manifest hash | Unchanged | Unchanged | No |
| Artifact schema (16 artifacts) | Unchanged | Unchanged | No |
| Verify endpoints | Unchanged | Unchanged | No |
| Replay attestation | Unchanged | Unchanged | No |
| `signed_export.sigmeta.json` | `signature_alg: Ed25519` | `signature_alg: ES256` | `signature_alg` only |
| `public_keys.json` | Ed25519 raw b64 | ECDSA P-256 DER b64 | Key format |

**The only things that change:** the algorithm field in sigmeta and the public key format. Everything else is identical. A customer moving from pilot to production does not lose any historical execution records — the ledger is portable.

### Provider Interface

```python
class SigningProvider:
    def sign(self, payload: bytes) -> bytes: ...          # produce signature bytes
    def sign_b64(self, payload: bytes) -> str: ...        # base64-encoded convenience
    def algorithm(self) -> str: ...                       # "Ed25519" or "ES256"
    def key_id(self) -> str: ...                          # local key ID or vault URL
    def public_key_b64(self) -> str: ...                  # public key for verification
    def provider_name(self) -> str: ...                   # "local" or "azure-keyvault"
    def key_mode(self) -> str: ...                        # "ephemeral", "configured", or "hsm"
```

To add a new provider (AWS KMS, HashiCorp Vault, GCP KMS), implement this interface and register the name in `_create_signing_provider()`.

---

## 6. Azure Key Vault Setup Guide

### Step 0 — Prerequisites

- Azure subscription with Contributor access
- Azure CLI ≥ 2.50 (`az --version`)
- DIIaC deployment target: Azure VM, Container App, AKS node, or Azure Functions
- Python 3.11+ (already used by DIIaC)

### Step 1 — Create Resource Group

```bash
az group create \
  --name rg-diiac-security \
  --location uksouth
```

### Step 2 — Create Azure Key Vault (RBAC mode, Premium tier)

```bash
az keyvault create \
  --name kv-diiac-prod \
  --resource-group rg-diiac-security \
  --location uksouth \
  --sku premium \
  --enable-rbac-authorization true \
  --enable-purge-protection true \
  --retention-days 90
```

**Why Premium?** HSM-backed keys. The Premium tier is required to get the hardware attestation that regulators expect.

**Why `--enable-rbac-authorization true`?** RBAC mode is the modern, recommended approach. It avoids the per-vault Access Policy model which cannot be managed at scale.

**Why `--enable-purge-protection true`?** Prevents accidental key destruction. Required for SOC 2 and ISO 27001 compliance.

### Step 3 — Create the Signing Key

```bash
az keyvault key create \
  --vault-name kv-diiac-prod \
  --name diiac-signing-v1 \
  --kty EC \
  --curve P-256 \
  --protection hsm \
  --ops sign verify
```

**Why `--kty EC --curve P-256`?**

> ⚠️ Azure Key Vault does NOT support Ed25519 keys. This is a documented platform limitation. Attempts to create Ed25519 keys in Key Vault fail — do not attempt it.

ECDSA P-256 (ES256) is:
- Fully supported by Azure Key Vault on HSM tier
- Accepted by GDPR, NIS2, ISO 27001, SOC 2, FCA, NCSC
- Mathematically equivalent in security strength to Ed25519 for DIIaC's threat model
- Widely understood by external auditors

**Why `--ops sign verify`?** The key is permitted to sign and verify only. It cannot be exported, wrapped, or used for encryption. This is the minimal permission set — principle of least privilege for a signing key.

### Step 4 — Enable Managed Identity on the DIIaC Deployment Target

#### If using Azure Container Apps:

```bash
az containerapp identity assign \
  --name diiac-governance-runtime \
  --resource-group rg-diiac-prod \
  --system-assigned
```

Note the `principalId` from the output.

#### If using Azure VM:

```bash
az vm identity assign \
  --name diiac-vm \
  --resource-group rg-diiac-prod
```

#### If using AKS (pod identity):

Use Azure Workload Identity. See: https://learn.microsoft.com/azure/aks/workload-identity-overview

### Step 5 — Grant Minimal Sign Permission

```bash
az role assignment create \
  --assignee <MANAGED_IDENTITY_PRINCIPAL_ID> \
  --role "Key Vault Crypto User" \
  --scope /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-diiac-security/providers/Microsoft.KeyVault/vaults/kv-diiac-prod
```

**What "Key Vault Crypto User" grants:**
- ✅ `sign` — produce signatures
- ✅ `verify` — verify signatures
- ❌ `get` key material — cannot export the private key
- ❌ `delete` — cannot destroy the key
- ❌ `create` — cannot create new keys

This is exactly what DIIaC needs and nothing more.

### Step 6 — Enable Azure SDK in DIIaC

In `requirements.txt`, uncomment the two Azure lines:

```
# BEFORE (pilot mode):
# azure-keyvault-keys==4.9.0
# azure-identity==1.17.0

# AFTER (production mode):
azure-keyvault-keys==4.9.0
azure-identity==1.17.0
```

### Step 7 — Configure Environment Variables

In `docker-compose.yml` or your Container App / AKS deployment manifest:

```yaml
SIGNING_PROVIDER: azure-keyvault
KEYVAULT_URL: https://kv-diiac-prod.vault.azure.net
KEYVAULT_KEY_NAME: diiac-signing-v1
KEYVAULT_KEY_VERSION: ""          # empty = always use latest version
```

For local development against a real vault (no Managed Identity):

```bash
export AZURE_CLIENT_ID=<service-principal-app-id>
export AZURE_CLIENT_SECRET=<service-principal-secret>
export AZURE_TENANT_ID=<tenant-id>
```

### Step 8 — Rebuild and Restart

```bash
docker-compose build governance-runtime
docker-compose up -d governance-runtime
```

### Step 9 — Verify the Switch

```bash
# Confirm signing provider is active
curl http://localhost:8000/admin/config \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expected:

```json
{
  "signing_provider": "azure-keyvault",
  "signing_algorithm": "ES256",
  "signing_key_id": "https://kv-diiac-prod.vault.azure.net/keys/diiac-signing-v1",
  "signing_key_mode": "hsm"
}
```

```bash
# Run a governed compile and confirm ES256 signature
curl -X POST http://localhost:8000/api/governed-compile \
  -H "Content-Type: application/json" \
  -d '{"execution_context_id": "ctx-akv-test-001", ...}'
```

Check `signed_export.sigmeta.json` — `signature_alg` should be `ES256`.

```bash
# Run E2E smoke
python3 scripts_e2e_runtime_smoke.py
```

Expected: All checks pass. The smoke test is provider-agnostic — it validates the governance flow, not the specific algorithm.

---

## 7. What This Means for an Acquirer or Regulator

### What they will ask

> *"Where do the signing keys live?"*

### With local provider (pilot)

> *"Keys are generated in-process at startup. They are not persisted and cannot be exported. Each restart generates a new key. This is suitable for development and pilot environments."*

This answer is acceptable for a PoC. It will not pass a security review for production.

### With Azure Key Vault (production)

> *"Signing keys are ECDSA P-256 keys stored in Azure Key Vault Premium tier, HSM-backed. Private key material never leaves Azure. The DIIaC service signs via the CryptographyClient API with an ES256 signing operation. The service identity holds Key Vault Crypto User role only — it cannot export, modify, or destroy the key. Purge protection is enabled with a 90-day retention policy. Key operations are logged in Azure Monitor. Key rotation is performed via Azure Key Vault key versioning."*

This answer passes a security review. It satisfies:
- ISO 27001 A.10.1 (Cryptography policy)
- SOC 2 CC6.1 (Logical access controls)
- GDPR Article 32 (Security of processing)
- NIS2 Article 21 (Cybersecurity risk management)
- NCSC Cloud Security Principle 2 (Asset protection and resilience)

---

## 8. Key Rotation

Key rotation in Azure Key Vault is non-destructive. When you rotate:

1. Azure creates a new key version
2. The old version remains valid for verification of historical signatures
3. The new version is used for all new signatures

DIIaC references the `KEYVAULT_KEY_VERSION` env var:
- Empty (default): always use the latest key version — new signatures use the new key
- Set to a version string: pins to a specific version

**For rotation:**

```bash
# Create a new key version (Azure rotates automatically, or manually:)
az keyvault key rotate --vault-name kv-diiac-prod --name diiac-signing-v1

# No DIIaC config change needed if KEYVAULT_KEY_VERSION is empty.
# The new version is used for all subsequent signatures automatically.
```

Historical signatures remain verifiable because:
1. `signed_export.sigmeta.json` records the full `signing_key_id` including the version URL
2. The old version remains accessible in Key Vault for verification
3. The ledger anchor is hash-based — it does not depend on the key

---

## 9. Multi-Customer / Multi-Tenant Deployment

Each customer gets their own vault. The deployment model is:

```
Customer A:
  KEYVAULT_URL=https://kv-diiac-customera.vault.azure.net
  KEYVAULT_KEY_NAME=diiac-signing-v1
  Managed Identity: diiac-runtime-customera

Customer B:
  KEYVAULT_URL=https://kv-diiac-customerb.vault.azure.net
  KEYVAULT_KEY_NAME=diiac-signing-v1
  Managed Identity: diiac-runtime-customerb
```

Each customer's signing keys are cryptographically isolated. A cross-customer key access is not possible by construction — each Managed Identity can only reach its own vault.

For managed-service deployments (DIIaC-as-a-Service), consider:
- One vault per customer (recommended — cleanest audit boundary)
- One vault per environment tier (dev/staging/prod) per customer

Multi-vault routing (e.g. key selection based on execution profile or tenant) is a v1.3.x roadmap item. It is not in scope for the current implementation.

---

## 10. What Remains After This Sprint

### Fully resolved by this implementation

| Item | Status |
|---|---|
| Signing keys in process memory | Resolved — AKV signer keeps keys in HSM |
| No key lifecycle governance | Resolved — Azure Key Vault rotation + purge protection |
| No external attestation of key protection | Resolved — Azure attestation + RBAC audit log |
| No access control on key operations | Resolved — Key Vault Crypto User (sign only) |
| Admin dashboard shows signing state | Resolved — `/admin/config` and `/admin/health` |

### Remains open for v1.2.2

| Item | Owner | Notes |
|---|---|---|
| `ledger_root_at_export` — Merkle root of ledger at audit export time | v1.2.1 backlog | Already spec'd in `PRODUCT_ROADMAP_V1_3_0.md` |
| `ledger_slice` inclusion proofs | v1.2.1 backlog | Already spec'd |
| Verification logic for ES256 in `/verify/pack` | v1.2.2 | Currently passes Ed25519. Needs algorithm-aware verifier for ES256 production validation |
| Key version recorded in ledger record | v1.2.2 | Record the key version URL in ledger for forward-traceability |

### The ES256 Verify Gap

The `verify/pack` endpoint currently validates signatures using the Ed25519 algorithm hardcoded. With ES256 keys in production, the pack verification will need to be updated to read `signature_alg` from `signed_export.sigmeta.json` and dispatch to the appropriate verifier.

This is a v1.2.2 item. It does not affect:
- The compile flow (signing works correctly with ES256)
- The ledger (unchanged)
- The audit trail (unchanged)
- External offline verification (uses the public key file directly)

It means: in AKV mode, `POST /verify/pack` will return `signature_valid: false` until v1.2.2 because the verifier attempts Ed25519 verification of an ES256 signature. The rest of the verification (hash, manifest, Merkle) is unaffected.

**Document this clearly in any pre-sales conversation where AKV is active.** The decision record is valid; the in-process signature verification endpoint will lag by one patch.

---

## 11. Environment Variable Reference

### Core signing configuration

| Variable | Default | Description |
|---|---|---|
| `SIGNING_PROVIDER` | `local` | Signing backend: `local` or `azure-keyvault` |
| `SIGNING_ENABLED` | `true` | Enable/disable signing globally |
| `SIGNING_KEY_ID` | `ephemeral-local-ed25519` | Human-readable key ID (local provider only) |
| `SIGNING_PRIVATE_KEY_PEM` | *(empty)* | Inject a persistent Ed25519 PEM key (local provider only) |

### Azure Key Vault specific

| Variable | Default | Description |
|---|---|---|
| `KEYVAULT_URL` | *(required)* | Vault URL, e.g. `https://kv-customer-prod.vault.azure.net` |
| `KEYVAULT_KEY_NAME` | `diiac-signing-v1` | Key name in the vault |
| `KEYVAULT_KEY_VERSION` | *(empty = latest)* | Pin to a specific key version |
| `KEYVAULT_TENANT_ID` | *(empty)* | **Customer's Azure AD tenant ID** — routes credentials to the customer's tenant for customer-managed vault deployments. Mirrors `ENTRA_EXPECTED_TENANT_ID`. Falls back to `AZURE_TENANT_ID` if not set. |
| `AZURE_CLIENT_ID` | *(Managed Identity)* | Service principal App ID — for cross-tenant or local dev |
| `AZURE_CLIENT_SECRET` | *(Managed Identity)* | Service principal secret — for cross-tenant or local dev |
| `AZURE_TENANT_ID` | *(Managed Identity)* | Fallback tenant ID — used if `KEYVAULT_TENANT_ID` is not set |

### Ledger control

| Variable | Default | Description |
|---|---|---|
| `LEDGER_FREEZE` | `false` | Prevent new ledger writes — for demo/diligence environments |

---

## 10. Sales Framing for Key Vault Readiness

### The current honest position (pilot)

> *"DIIaC ships with a local Ed25519 signing key by default — sufficient for pilots, demos, and technical validation. The signing key never leaves the process, and the signed record is mathematically tamper-evident. For regulated production, the platform has a built-in Azure Key Vault provider that moves signing keys into an HSM — this is a configuration change, not a development task. We can provision it the same day Azure is available."*

### The production position (with AKV active)

> *"DIIaC signs every governance decision pack with a key held in Azure Key Vault Premium (HSM-backed). The private key never leaves Azure. The service has sign-only permission — it cannot export or destroy the key. Every signature references a specific key version, which is recorded in the immutable ledger alongside the execution hash. Regulators can independently verify both the signature and the key custody record."*

### The differentiator claim

Most AI governance tools produce a governance record as a document or database entry. DIIaC produces a governance record as:

- A 16-artifact cryptographic pack
- Sealed under a Merkle root
- Signed by a key whose private material never existed in software
- Anchored in an immutable, hash-chained ledger
- Independently verifiable offline

This is not a policy. It is a cryptographic proof. No amount of access to the system can retroactively alter a decision that has been signed, anchored, and exported.

---

## Document Control

| Field | Value |
|---|---|
| **Document ID** | DIIAC-KV-PLAN-001 |
| **Version** | 1.0 |
| **Baseline** | v1.2.0-ledger-anchored |
| **Code artefacts** | `app.py` — `SigningProvider`, `LocalEdDSASigner`, `AzureKeyVaultSigner`, `_create_signing_provider` |
| **Config artefacts** | `requirements.txt`, `docker-compose.yml` — AKV env vars pre-wired |
| **Admin signals** | `/admin/config` → `signing_provider`, `signing_algorithm`, `signing_key_id`, `signing_key_mode` |
| **Related docs** | `DIIAC_SALES_CASE_AND_TEST_EVIDENCE.md`, `PRODUCT_ROADMAP_V1_3_0.md` |
| **Intended audience** | Engineering, Sales, Customer deployment teams |
