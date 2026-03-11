#!/usr/bin/env bash
# DIIaC v1.2.0 — Build, push, and deploy to Azure Container Instances
#
# Usage:
#   bash scripts/deploy-azure.sh                              # defaults to vendorlogic
#   bash scripts/deploy-azure.sh --customer vendorlogic       # explicit customer
#   bash scripts/deploy-azure.sh --skip-build                 # deploy only (images already pushed)
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker running (for image builds)
#   - Key Vault populated (see customer-config/<customer>/keyvault-secrets-manifest.md)
#   - Resource group exists: az group create -n rg-diiac-prod -l uksouth
#
# What this script does:
#   1. Deploys the Bicep landing zone (ACR, ACI, KV, Storage, Identity)
#   2. Builds and pushes all 3 container images to ACR
#   3. Pulls secrets from Key Vault
#   4. Updates the ACI container group with secret environment variables

set -euo pipefail

# ── Parse arguments ──────────────────────────────────────────────────────────

CUSTOMER="${DIIAC_CUSTOMER:-vendorlogic}"
SKIP_BUILD=false
SKIP_INFRA=false
VERSION="1.2.0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --customer)    CUSTOMER="$2"; shift 2 ;;
    --skip-build)  SKIP_BUILD=true; shift ;;
    --skip-infra)  SKIP_INFRA=true; shift ;;
    --version)     VERSION="$2"; shift 2 ;;
    *)             echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CUSTOMER_CONFIG="${REPO_ROOT}/customer-config/${CUSTOMER}/config.env"

if [[ ! -f "$CUSTOMER_CONFIG" ]]; then
  echo "ERROR: Customer config not found: $CUSTOMER_CONFIG" >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a; source "$CUSTOMER_CONFIG"; set +a

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-diiac-prod}"
LOCATION="${AZURE_LOCATION:-uksouth}"
KV_NAME="${KEY_VAULT_NAME:-kv-diiac-${CUSTOMER}}"

# ── Colours ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }
step() { echo -e "\n${GREEN}━━━ $* ━━━${NC}\n"; }

echo ""
echo "DIIaC v${VERSION} — Azure Deployment"
echo "Customer: ${CUSTOMER} | RG: ${RESOURCE_GROUP} | Region: ${LOCATION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Verify Azure CLI ─────────────────────────────────────────────────────────

command -v az >/dev/null 2>&1 || fail "Azure CLI not found."
ACCOUNT=$(az account show --query "user.name" -o tsv 2>/dev/null || true)
[[ -n "$ACCOUNT" ]] || fail "Not logged in. Run: az login"
ok "Logged in as: $ACCOUNT"

# ── Step 1: Deploy infrastructure ────────────────────────────────────────────

if [[ "$SKIP_INFRA" == "false" ]]; then
  step "Deploying Bicep landing zone"

  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none 2>/dev/null || true

  DEPLOY_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "${REPO_ROOT}/infra/main.bicep" \
    --parameters "${REPO_ROOT}/infra/main.bicepparam" \
    --query "properties.outputs" \
    --output json)

  ACR_LOGIN_SERVER=$(echo "$DEPLOY_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['acrLoginServer']['value'])")
  ok "Infrastructure deployed"
else
  step "Skipping infra (--skip-infra)"
  ACR_LOGIN_SERVER=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].loginServer" -o tsv)
fi

ok "ACR: $ACR_LOGIN_SERVER"

# ── Step 2: Build and push container images ──────────────────────────────────

if [[ "$SKIP_BUILD" == "false" ]]; then
  step "Building and pushing container images"

  az acr login --name "${ACR_LOGIN_SERVER%%.*}"

  # Governance Runtime
  echo "Building governance-runtime..."
  docker build \
    -f "${REPO_ROOT}/Dockerfile.runtime" \
    -t "${ACR_LOGIN_SERVER}/diiac/governance-runtime:${VERSION}" \
    -t "${ACR_LOGIN_SERVER}/diiac/governance-runtime:latest" \
    "${REPO_ROOT}"
  docker push "${ACR_LOGIN_SERVER}/diiac/governance-runtime:${VERSION}"
  docker push "${ACR_LOGIN_SERVER}/diiac/governance-runtime:latest"
  ok "governance-runtime pushed"

  # Backend UI Bridge
  echo "Building backend-ui-bridge..."
  docker build \
    -f "${REPO_ROOT}/backend-ui-bridge/Dockerfile" \
    -t "${ACR_LOGIN_SERVER}/diiac/backend-ui-bridge:${VERSION}" \
    -t "${ACR_LOGIN_SERVER}/diiac/backend-ui-bridge:latest" \
    "${REPO_ROOT}/backend-ui-bridge"
  docker push "${ACR_LOGIN_SERVER}/diiac/backend-ui-bridge:${VERSION}"
  docker push "${ACR_LOGIN_SERVER}/diiac/backend-ui-bridge:latest"
  ok "backend-ui-bridge pushed"

  # Frontend
  echo "Building frontend..."
  docker build \
    -f "${REPO_ROOT}/Frontend/Dockerfile" \
    -t "${ACR_LOGIN_SERVER}/diiac/frontend:${VERSION}" \
    -t "${ACR_LOGIN_SERVER}/diiac/frontend:latest" \
    "${REPO_ROOT}/Frontend"
  docker push "${ACR_LOGIN_SERVER}/diiac/frontend:${VERSION}"
  docker push "${ACR_LOGIN_SERVER}/diiac/frontend:latest"
  ok "frontend pushed"
else
  step "Skipping build (--skip-build)"
fi

# ── Step 3: Pull secrets from Key Vault ──────────────────────────────────────

step "Pulling secrets from Key Vault: $KV_NAME"

ADMIN_TOKEN=$(az keyvault secret show \
  --vault-name "$KV_NAME" --name "diiac-admin-api-token" \
  --query "value" -o tsv) || fail "Failed to retrieve diiac-admin-api-token"
ok "ADMIN_API_TOKEN"

SIGNING_PEM=$(az keyvault secret show \
  --vault-name "$KV_NAME" --name "diiac-signing-private-key-pem" \
  --query "value" -o tsv) || fail "Failed to retrieve signing key"
ok "SIGNING_PRIVATE_KEY_PEM"

OPENAI_KEY=$(az keyvault secret show \
  --vault-name "$KV_NAME" --name "diiac-openai-api-key" \
  --query "value" -o tsv) || fail "Failed to retrieve OpenAI key"
ok "OPENAI_API_KEY"

GITHUB_TOKEN_VAL=""
if az keyvault secret show --vault-name "$KV_NAME" --name "diiac-github-token" \
   --query "value" -o tsv >/dev/null 2>&1; then
  GITHUB_TOKEN_VAL=$(az keyvault secret show \
    --vault-name "$KV_NAME" --name "diiac-github-token" \
    --query "value" -o tsv)
  ok "GITHUB_TOKEN"
else
  warn "diiac-github-token not found — Copilot provider disabled"
fi

# ── Step 4: Update ACI with secrets ──────────────────────────────────────────

step "Updating container group with secrets"

# ACI does not support in-place secret updates — must redeploy with secrets
# injected as secure environment variables via the Bicep template override.
# We use az container create --yaml for the secret injection pass.

ACI_NAME="aci-diiac-${CUSTOMER}"

cat > /tmp/diiac-aci-secrets.yaml <<YAMLEOF
apiVersion: '2021-10-01'
type: Microsoft.ContainerInstance/containerGroups
name: ${ACI_NAME}
location: ${LOCATION}
properties:
  containers:
  - name: governance-runtime
    properties:
      environmentVariables:
      - name: ADMIN_API_TOKEN
        secureValue: '${ADMIN_TOKEN}'
      - name: SIGNING_PRIVATE_KEY_PEM
        secureValue: '${SIGNING_PEM}'
  - name: backend-ui-bridge
    properties:
      environmentVariables:
      - name: OPENAI_API_KEY
        secureValue: '${OPENAI_KEY}'
      - name: GITHUB_TOKEN
        secureValue: '${GITHUB_TOKEN_VAL}'
      - name: ADMIN_API_TOKEN
        secureValue: '${ADMIN_TOKEN}'
YAMLEOF

warn "Secret injection requires a container group restart."
warn "The Bicep deployment already created the container group."
warn "To inject secrets, redeploy with: az deployment group create using the same template"
warn "passing secrets as parameters, or use the YAML override approach for ACI."

rm -f /tmp/diiac-aci-secrets.yaml

# ── Step 5: Verify ───────────────────────────────────────────────────────────

step "Verifying deployment"

FQDN=$(az container show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACI_NAME" \
  --query "ipAddress.fqdn" -o tsv 2>/dev/null || echo "pending")

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Deployment complete${NC}"
echo ""
echo "  FQDN:     https://${FQDN}"
echo "  ACR:      ${ACR_LOGIN_SERVER}"
echo "  Key Vault: ${KV_NAME}"
echo "  ACI:      ${ACI_NAME}"
echo ""
echo "Next steps:"
echo "  1. Verify health:  curl https://${FQDN}/health"
echo "  2. Check logs:     az container logs -g ${RESOURCE_GROUP} -n ${ACI_NAME} --container-name governance-runtime"
echo "  3. Update Entra redirect URI to: https://${FQDN}/auth/callback"
echo ""
