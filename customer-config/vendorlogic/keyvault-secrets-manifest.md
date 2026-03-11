# Vendorlogic — Key Vault Secrets Manifest

**Key Vault:** `kv-diiac-vendorlogic`
**Resource Group:** `RG_Root`
**Subscription ID:** `3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7`
**Region:** `uksouth`

These are the secrets that must exist in the Key Vault before running the
pull script or deploying to production. No values are stored here — values
live only in Key Vault.

| Secret Name | Type | Rotation | Description |
|-------------|------|----------|-------------|
| `diiac-admin-api-token` | Random hex | 90 days | Bearer token for all `/admin/*` endpoints. Generate: `openssl rand -hex 32` |
| `diiac-signing-private-key-pem` | Ed25519 PEM | On compromise only | Private signing key for all decision pack exports. Rotating breaks existing signature verification. |
| `diiac-openai-api-key` | OpenAI API key | 90 days | `sk-...` key from platform.openai.com. Scoped to gpt-4o-mini minimum. |
| `diiac-entra-client-secret` | Entra secret | 12 months | Client secret for DIIaC-API-Vendorlogic app registration. Rotate via Entra portal. **Optional** — bridge uses JWKS-only RS256 validation and does not require a client secret. |

## Service accounts

| Account | UPN | Object ID | Role required |
|---------|-----|-----------|---------------|
| `SVC-DIIAC-AKV` | `SVC-DIIAC-AKV@vendorlogic.io` | `280538b4-7fe3-45fd-a8d0-650d573a19eb` | Key Vault Secrets User |

```bash
# Assign Key Vault Secrets User to SVC-DIIAC-AKV
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee "280538b4-7fe3-45fd-a8d0-650d573a19eb" \
  --scope "/subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_Root/providers/Microsoft.KeyVault/vaults/kv-diiac-vendorlogic"

# Assign Key Vault Secrets User to nbailey (operator / local staging)
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee "nbailey@vendorlogic.io" \
  --scope "/subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_Root/providers/Microsoft.KeyVault/vaults/kv-diiac-vendorlogic"
```

## Provision checklist

### Vault infrastructure (complete)
- [x] Key Vault `kv-diiac-vendorlogic` created in `RG_Root` (uksouth)
- [x] RBAC authorisation model enabled
- [x] Soft-delete enabled (90 days)
- [x] Purge protection enabled

### Secrets (populate before first pull-script run)
- [x] `diiac-admin-api-token` stored — `openssl rand -hex 32`
- [x] `diiac-signing-private-key-pem` stored — Ed25519 PKCS8 PEM, LF line endings (see Generate signing key below)
- [x] `diiac-openai-api-key` stored — `sk-...` from platform.openai.com
- [x] `diiac-entra-client-secret` stored *(optional — bridge does not require it)*

### Access control
- [x] `SVC-DIIAC-AKV` (OID: `280538b4-7fe3-45fd-a8d0-650d573a19eb`) granted `Key Vault Secrets Officer` *(note: over-privileged — downgrade to Secrets User when convenient)*
- [ ] `nbailey@vendorlogic.io` granted `Key Vault Secrets User` (local staging — required to run pull script)
- [ ] VM / AKS managed identity granted `Key Vault Secrets User` role

## Generate signing key (one-time, per environment)

```bash
# Generate Ed25519 private key
openssl genpkey -algorithm ed25519 -out diiac_signing_key.pem

# Store in Key Vault
az keyvault secret set \
  --vault-name kv-diiac-vendorlogic \
  --name "diiac-signing-private-key-pem" \
  --file diiac_signing_key.pem

# Store public key in contracts/keys/public_keys.json (commit this)
openssl pkey -in diiac_signing_key.pem -pubout

# Shred local copy after storing in Key Vault
shred -uz diiac_signing_key.pem
```

## Rotation procedure — Admin token

```bash
NEW_TOKEN=$(openssl rand -hex 32)
az keyvault secret set --vault-name kv-diiac-vendorlogic \
  --name "diiac-admin-api-token" --value "$NEW_TOKEN"
# Re-pull secrets and restart stack
bash scripts/pull-keyvault-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.staging.yml restart
```
