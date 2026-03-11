# Vendorlogic — Key Vault Secrets Manifest

**Key Vault:** `kv-diiac-vendorlogic`
**Resource Group:** `rg-diiac-prod`
**Region:** `uksouth`

These are the secrets that must exist in the Key Vault before running the
pull script or deploying to production. No values are stored here — values
live only in Key Vault.

| Secret Name | Type | Rotation | Description |
|-------------|------|----------|-------------|
| `diiac-admin-api-token` | Random hex | 90 days | Bearer token for all `/admin/*` endpoints. Generate: `openssl rand -hex 32` |
| `diiac-signing-private-key-pem` | Ed25519 PEM | On compromise only | Private signing key for all decision pack exports. Rotating breaks existing signature verification. |
| `diiac-openai-api-key` | OpenAI API key | 90 days | `sk-...` key from platform.openai.com. Scoped to gpt-4o-mini minimum. |
| `diiac-entra-client-secret` | Entra secret | 12 months | Client secret for DIIaC-API-Vendorlogic app registration. Rotate via Entra portal. |

## Provision checklist

- [ ] Key Vault created with RBAC auth model (`--enable-rbac-authorization true`)
- [ ] Soft-delete enabled (default on new vaults)
- [ ] Purge protection enabled: `az keyvault update --enable-purge-protection true`
- [ ] `diiac-admin-api-token` stored
- [ ] `diiac-signing-private-key-pem` stored (Ed25519 PKCS8 PEM, LF line endings)
- [ ] `diiac-openai-api-key` stored
- [ ] `diiac-entra-client-secret` stored
- [ ] VM / AKS managed identity granted `Key Vault Secrets User` role
- [ ] Developer accounts granted `Key Vault Secrets User` role (for local staging)

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
