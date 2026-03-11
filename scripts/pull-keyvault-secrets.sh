#!/usr/bin/env bash
# DIIaC v1.2.0 — Pull secrets from Azure Key Vault for local Docker Desktop staging
#
# Usage:
#   bash scripts/pull-keyvault-secrets.sh                         # defaults to vendorlogic
#   bash scripts/pull-keyvault-secrets.sh --customer acmecorp     # use acmecorp config
#   DIIAC_CUSTOMER=acmecorp bash scripts/pull-keyvault-secrets.sh # env var alternative
#
# Prerequisites:
#   - Azure CLI installed (https://learn.microsoft.com/cli/azure/install-azure-cli)
#   - az login completed
#   - Key Vault populated (see customer-config/<customer>/keyvault-secrets-manifest.md)
#
# Outputs:
#   .env                      — all non-PEM secrets for docker compose
#   .secrets/signing_key.pem  — Ed25519 signing key (bind-mounted by compose)
#
# Run from the repository root.

set -euo pipefail

# ── Customer selection ──────────────────────────────────────────────────────
# Accept --customer flag or DIIAC_CUSTOMER env var, default to "vendorlogic"
CUSTOMER="${DIIAC_CUSTOMER:-vendorlogic}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --customer) CUSTOMER="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Configuration — loaded from customer config ─────────────────────────────
# These are public identifiers (app registration IDs, group OIDs).
# Safe to commit. Override any value by exporting it before running this script.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CUSTOMER_CONFIG="${REPO_ROOT}/customer-config/${CUSTOMER}/config.env"
if [[ ! -f "$CUSTOMER_CONFIG" ]]; then
  echo "Customer config not found: $CUSTOMER_CONFIG" >&2
  echo "  Create it by copying: customer-config/_template/config.env" >&2
  echo "  Then fill in the REPLACE_WITH_* placeholders for your customer." >&2
  exit 1
fi
# shellcheck source=/dev/null
set -a; source "$CUSTOMER_CONFIG"; set +a

KV_NAME="${KEY_VAULT_NAME:-kv-diiac-vendorlogic}"
ENTRA_TENANT_ID="${AZURE_TENANT_ID:-1384b1c5-2bae-45a1-a4b4-e94e3315eb41}"
ENTRA_API_APP_ID="${ENTRA_API_APP_ID:-b726558d-f1c6-48f7-8a3d-72d5db818d0f}"
ENTRA_UI_APP_ID="${ENTRA_UI_APP_ID:-b726558d-f1c6-48f7-8a3d-72d5db818d0f}"
ENTRA_ADMIN_GROUP_ID="${ENTRA_ADMIN_GROUP_ID:-81786818-de16-4115-b061-92fce74b00bd}"
ENTRA_USER_GROUP_ID="${ENTRA_STANDARD_GROUP_ID:-9c7dd0d4-5b44-4811-b167-e52df21092d8}"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

echo ""
echo "DIIaC v1.2.0 — Key Vault secret pull"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check az CLI ──────────────────────────────────────────────────────────────
command -v az >/dev/null 2>&1 || fail "Azure CLI not found. Install: https://aka.ms/InstallAzureCLIDeb"

# ── Check login ───────────────────────────────────────────────────────────────
ACCOUNT=$(az account show --query "user.name" -o tsv 2>/dev/null || true)
if [[ -z "$ACCOUNT" ]]; then
  warn "Not logged in to Azure CLI. Running az login..."
  az login
  ACCOUNT=$(az account show --query "user.name" -o tsv)
fi
ok "Logged in as: $ACCOUNT"

# Auto-detect Tenant ID if not set
if [[ -z "$ENTRA_TENANT_ID" ]]; then
  ENTRA_TENANT_ID=$(az account show --query tenantId -o tsv)
  warn "ENTRA_TENANT_ID not set — using active tenant: $ENTRA_TENANT_ID"
fi

# ── Check Key Vault exists ────────────────────────────────────────────────────
az keyvault show --name "$KV_NAME" --query name -o tsv >/dev/null 2>&1 || \
  fail "Key Vault '$KV_NAME' not found. Check KV_NAME or run the provisioning steps first."
ok "Key Vault found: $KV_NAME"

# ── Create .secrets directory ─────────────────────────────────────────────────
mkdir -p .secrets
chmod 700 .secrets
ok ".secrets/ directory ready"

# ── Pull signing key PEM → file (avoids .env multiline issues) ────────────────
echo ""
echo "Pulling signing key from Key Vault..."
az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name "diiac-signing-private-key-pem" \
  --query "value" -o tsv > .secrets/signing_key.pem
chmod 600 .secrets/signing_key.pem

# Verify it looks like a valid PEM
head -1 .secrets/signing_key.pem | grep -q "BEGIN" || \
  fail "Signing key PEM appears malformed. Check Key Vault secret 'diiac-signing-private-key-pem'."
ok "Signing key → .secrets/signing_key.pem"

# ── Pull non-PEM secrets ──────────────────────────────────────────────────────
echo ""
echo "Pulling secrets..."

ADMIN_TOKEN=$(az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name "diiac-admin-api-token" \
  --query "value" -o tsv)
ok "ADMIN_API_TOKEN retrieved (${#ADMIN_TOKEN} chars)"

OPENAI_KEY=$(az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name "diiac-openai-api-key" \
  --query "value" -o tsv)
ok "OPENAI_API_KEY retrieved"

# GitHub token (used by the bridge for Copilot / GitHub Models API)
GITHUB_TOKEN_VAL=""
if az keyvault secret show --vault-name "$KV_NAME" --name "diiac-github-token" \
   --query "value" -o tsv >/dev/null 2>&1; then
  GITHUB_TOKEN_VAL=$(az keyvault secret show \
    --vault-name "$KV_NAME" \
    --name "diiac-github-token" \
    --query "value" -o tsv)
  ok "GITHUB_TOKEN retrieved"
else
  warn "diiac-github-token not found in Key Vault — Copilot LLM provider will be unavailable"
fi

# Entra client secret (used by the bridge for token validation context)
ENTRA_SECRET=""
if az keyvault secret show --vault-name "$KV_NAME" --name "diiac-entra-client-secret" \
   --query "value" -o tsv >/dev/null 2>&1; then
  ENTRA_SECRET=$(az keyvault secret show \
    --vault-name "$KV_NAME" \
    --name "diiac-entra-client-secret" \
    --query "value" -o tsv)
  ok "ENTRA_CLIENT_SECRET retrieved"
else
  warn "diiac-entra-client-secret not found in Key Vault — Entra auth will use JWKS only"
fi

# ── Build .env ────────────────────────────────────────────────────────────────
echo ""
echo "Writing .env..."

cat > .env <<ENVEOF
# DIIaC v1.2.0 — ${CUSTOMER} local staging
# Generated by scripts/pull-keyvault-secrets.sh --customer ${CUSTOMER} on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# DO NOT COMMIT — this file contains secrets

# ── Ports ─────────────────────────────────────────────────────────────────────
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173

# ── Runtime secrets ───────────────────────────────────────────────────────────
ADMIN_API_TOKEN=${ADMIN_TOKEN}

# ── LLM ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_MODEL=gpt-4o-mini
GITHUB_TOKEN=${GITHUB_TOKEN_VAL}
COPILOT_MODEL=gpt-4o

# ── Entra ID ──────────────────────────────────────────────────────────────────
AUTH_MODE=entra_jwt_rs256
ENTRA_ROLE_CLAIM=roles
ENTRA_EXPECTED_TENANT_ID=${ENTRA_TENANT_ID}
ENTRA_EXPECTED_AUDIENCE=api://${ENTRA_API_APP_ID}
ENTRA_EXPECTED_ISSUERS=https://login.microsoftonline.com/${ENTRA_TENANT_ID}/v2.0,https://sts.windows.net/${ENTRA_TENANT_ID}/
ENTRA_GROUP_TO_ROLE_JSON={"${ENTRA_ADMIN_GROUP_ID}":{"role":"admin"},"${ENTRA_USER_GROUP_ID}":{"role":"standard"}}
ENTRA_PRINCIPAL_TO_ROLE_JSON={}
ENTRA_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/${ENTRA_TENANT_ID}/v2.0/.well-known/openid-configuration
ENTRA_JWKS_URI=https://login.microsoftonline.com/${ENTRA_TENANT_ID}/discovery/v2.0/keys

# ── Frontend MSAL ─────────────────────────────────────────────────────────────
VITE_ENTRA_CLIENT_ID=${ENTRA_UI_APP_ID}
VITE_ENTRA_TENANT_ID=${ENTRA_TENANT_ID}
VITE_ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_ENTRA_GROUP_MAP={"${ENTRA_ADMIN_GROUP_ID}":{"role":"admin"},"${ENTRA_USER_GROUP_ID}":{"role":"standard"}}
ENVEOF

chmod 600 .env
ok ".env written"

# ── Warn if Entra IDs are placeholders ───────────────────────────────────────
echo ""
if [[ -z "$ENTRA_API_APP_ID" || "$ENTRA_API_APP_ID" == "" ]]; then
  warn "ENTRA_API_APP_ID is not set."
  warn "Set it at the top of this script or export ENTRA_API_APP_ID=<your-app-id> before running."
fi
if [[ -z "$ENTRA_ADMIN_GROUP_ID" || "$ENTRA_ADMIN_GROUP_ID" == "" ]]; then
  warn "ENTRA_ADMIN_GROUP_ID / ENTRA_USER_GROUP_ID not set — group RBAC mapping will be empty."
  warn "Update ENTRA_GROUP_TO_ROLE_JSON in .env manually after this script completes."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Secrets pulled successfully.${NC}"
echo ""
echo "Next step:"
echo "  docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build"
echo ""
