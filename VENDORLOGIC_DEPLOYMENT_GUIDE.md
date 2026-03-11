# DIIaC v1.2.0 — Vendorlogic First-Customer Deployment Guide

**Customer:** Vendorlogic
**Environment:** Azure Tenant + Azure Key Vault + Entra ID
**Target:** Fully production-operational DIIaC governance platform
**Version:** v1.2.0 (locked)

---

## Overview

This guide walks Vendorlogic through standing up DIIaC v1.2.0 end-to-end using:

- **Azure Key Vault** — All secrets (signing key, admin token, OpenAI key, Entra client secret)
- **Azure Entra ID** — SSO authentication for admin and standard users
- **Azure Container Apps or AKS** — Production hosting (both options covered)
- **Docker Compose on Azure VM** — Fastest path for initial validation

**Estimated time to first governed compile:** ~90 minutes (VM path) / ~3 hours (AKS path)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Vendorlogic Azure Tenant                                        │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐│
│  │  Entra ID        │    │  Azure Key Vault                     ││
│  │                 │    │                                       ││
│  │  App: DIIaC-UI  │    │  diiac-admin-api-token               ││
│  │  App: DIIaC-API │    │  diiac-signing-private-key-pem       ││
│  │                 │    │  diiac-openai-api-key                 ││
│  │  Groups:        │    │  diiac-entra-client-secret           ││
│  │   DIIaC-Admins  │    │                                       ││
│  │   DIIaC-Users   │    └──────────────────────────────────────┘│
│  └─────────────────┘                     │                      │
│                                          │ MSI / CSI            │
│  ┌───────────────────────────────────────▼──────────────────┐   │
│  │  DIIaC Stack                                              │   │
│  │                                                           │   │
│  │  [Frontend :5173] → [Bridge :3001] → [Runtime :8000]     │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Tools to install locally

```bash
# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az version

# Docker + Docker Compose (for VM path)
curl -fsSL https://get.docker.com | sh
docker compose version

# kubectl + helm (for AKS path)
az aks install-cli
helm version

# OpenSSL (for key generation)
openssl version
```

### Azure requirements

- Azure subscription with Contributor access
- Permission to create App Registrations in Entra ID
- Permission to create and configure Key Vaults

---

## Step 1 — Azure Login and Setup

```bash
# Login
az login

# Set your subscription
az account set --subscription "YOUR-SUBSCRIPTION-NAME-OR-ID"
az account show

# Set variables for this deployment
export SUBSCRIPTION_ID="3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7"
export RG="RG_Root"
export LOCATION="uksouth"
export KV_NAME="kv-diiac-vendorlogic"
export APP_NAME="diiac-vendorlogic"
export TENANT_ID=$(az account show --query tenantId -o tsv)

echo "Tenant ID: $TENANT_ID"
echo "Resource Group: $RG"
echo "Key Vault: $KV_NAME"
```

---

## Step 2 — Resource Group and Key Vault

> **Status: Already provisioned.** `kv-diiac-vendorlogic` exists in `RG_Root` (uksouth).
> RBAC authorisation, soft-delete (90 days), and purge protection are all enabled.
> Skip vault creation — proceed to RBAC assignments and secret population below.

### 2a — Grant Key Vault Secrets Officer to yourself (to populate secrets)

```bash
MY_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)

az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee $MY_OBJECT_ID \
  --scope $(az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)

echo "Key Vault Secrets Officer granted to $MY_OBJECT_ID"
```

### 2b — Grant Key Vault Secrets User to service account and operators

```bash
# SVC-DIIAC-AKV service account (OID: 280538b4-7fe3-45fd-a8d0-650d573a19eb)
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee "280538b4-7fe3-45fd-a8d0-650d573a19eb" \
  --scope $(az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)

# nbailey (operator, local staging)
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee "nbailey@vendorlogic.io" \
  --scope $(az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)

echo "RBAC assignments complete"
```

---

## Step 3 — Generate Secrets

### 3a — Admin API Token

```bash
# Generate a cryptographically random 32-byte hex token
ADMIN_TOKEN=$(openssl rand -hex 32)
echo "Admin token (save this securely): $ADMIN_TOKEN"
```

### 3b — Ed25519 Signing Key

```bash
# Generate Ed25519 private key in PKCS8 PEM format
openssl genpkey -algorithm ed25519 -out diiac_signing_key.pem
cat diiac_signing_key.pem

# Extract public key (keep for offline verification)
openssl pkey -in diiac_signing_key.pem -pubout -out diiac_signing_key_pub.pem
cat diiac_signing_key_pub.pem

# IMPORTANT: Back up diiac_signing_key.pem securely.
# Loss of this key means existing signatures cannot be verified.
```

### 3c — OpenAI API Key

Obtain from: https://platform.openai.com/api-keys

```bash
OPENAI_KEY="sk-..."   # Your key from OpenAI platform
```

---

## Step 4 — Populate Key Vault

```bash
# Store Admin API Token
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-admin-api-token" \
  --value "$ADMIN_TOKEN"

# Store Ed25519 Signing Key (PEM with newlines preserved)
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-signing-private-key-pem" \
  --file diiac_signing_key.pem

# Store OpenAI API Key
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-openai-api-key" \
  --value "$OPENAI_KEY"

# Verify all secrets are stored
az keyvault secret list --vault-name $KV_NAME -o table
```

---

## Step 5 — Entra ID App Registrations

DIIaC requires **two** app registrations:
1. **DIIaC-API** — Used by the backend-ui-bridge for JWT validation.
2. **DIIaC-UI** — Used by the React frontend for MSAL user sign-in.

### 5a — DIIaC-API registration (backend)

```bash
# Create the API app registration
API_APP=$(az ad app create \
  --display-name "DIIaC-API-Vendorlogic" \
  --query "appId" -o tsv)

echo "API App ID (client_id): $API_APP"

# Create a service principal for the app
az ad sp create --id $API_APP

# Create a client secret for the bridge to validate tokens with
API_SECRET=$(az ad app credential reset \
  --id $API_APP \
  --display-name "diiac-bridge-secret" \
  --query "password" -o tsv)

echo "API client secret (store in Key Vault): $API_SECRET"

# Store in Key Vault
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-entra-client-secret" \
  --value "$API_SECRET"

# Expose an API scope for the frontend to call
az ad app update \
  --id $API_APP \
  --identifier-uris "api://$API_APP"

# Add a scope: access_as_user
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/applications/$(az ad app show --id $API_APP --query id -o tsv)/api/oauth2PermissionScopes" \
  --body "{
    \"adminConsentDescription\": \"Access DIIaC as a user\",
    \"adminConsentDisplayName\": \"Access DIIaC\",
    \"id\": \"$(python3 -c 'import uuid; print(uuid.uuid4())')\",
    \"isEnabled\": true,
    \"type\": \"User\",
    \"userConsentDescription\": \"Allow this app to access DIIaC on your behalf\",
    \"userConsentDisplayName\": \"Access DIIaC\",
    \"value\": \"access_as_user\"
  }"

echo "DIIaC-API app: $API_APP"
echo "Tenant ID: $TENANT_ID"
```

### 5b — DIIaC-UI registration (frontend MSAL)

```bash
# Create the frontend app registration
UI_APP=$(az ad app create \
  --display-name "DIIaC-UI-Vendorlogic" \
  --query "appId" -o tsv)

echo "UI App ID: $UI_APP"

# Create service principal
az ad sp create --id $UI_APP

# Set redirect URIs (update with your actual domain)
az ad app update \
  --id $UI_APP \
  --web-redirect-uris "http://localhost:5173" "https://diiac.vendorlogic.com"

# Grant admin consent for the API scope
# (Tenant admin must run this, or grant via Azure Portal)
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" \
  --body "{
    \"clientId\": \"$(az ad sp show --id $UI_APP --query id -o tsv)\",
    \"consentType\": \"AllPrincipals\",
    \"resourceId\": \"$(az ad sp show --id $API_APP --query id -o tsv)\",
    \"scope\": \"access_as_user\"
  }"

echo "DIIaC-UI app: $UI_APP"
```

### 5c — Create Entra ID Groups for RBAC

```bash
# Create admin group
ADMIN_GROUP=$(az ad group create \
  --display-name "DIIaC-Admins" \
  --mail-nickname "DIIaC-Admins" \
  --query "id" -o tsv)

# Create standard user group
USER_GROUP=$(az ad group create \
  --display-name "DIIaC-Users" \
  --mail-nickname "DIIaC-Users" \
  --query "id" -o tsv)

echo "Admin Group ID:  $ADMIN_GROUP"
echo "User Group ID:   $USER_GROUP"

# Add yourself to admin group
az ad group member add --group "DIIaC-Admins" --member-id $MY_OBJECT_ID
```

### 5d — Configure group claims on the API app

In the **Azure Portal**:
1. Go to **Entra ID → App registrations → DIIaC-API-Vendorlogic**
2. Select **Token configuration**
3. Click **Add groups claim** → select **Security groups**
4. Under **ID**, **Access**, and **SAML** set the value to **Group ID**
5. Save

This ensures JWT tokens include the user's group membership, which the bridge
maps to `admin`, `standard`, or `customer` RBAC roles.

---

## Step 6A — Option A: Docker Compose on Azure VM (Fastest — ~90 min)

Best for: initial validation, development, low-traffic internal use.

### 6A.1 — Create Azure VM

```bash
VM_NAME="vm-diiac-prod"
VM_SIZE="Standard_B2s"   # 2 vCPU, 4GB RAM — sufficient for DIIaC

az vm create \
  --resource-group $RG \
  --name $VM_NAME \
  --image Ubuntu2204 \
  --size $VM_SIZE \
  --admin-username azureuser \
  --generate-ssh-keys \
  --assign-identity \
  --public-ip-sku Standard \
  --output table

# Open ports
az vm open-port --resource-group $RG --name $VM_NAME --port 443 --priority 1001
az vm open-port --resource-group $RG --name $VM_NAME --port 80 --priority 1002

# Get public IP
VM_IP=$(az vm show --resource-group $RG --name $VM_NAME -d --query publicIps -o tsv)
echo "VM IP: $VM_IP"
```

### 6A.2 — Grant VM Managed Identity access to Key Vault

```bash
# Get the VM's managed identity principal ID
VM_IDENTITY=$(az vm show \
  --resource-group $RG \
  --name $VM_NAME \
  --query identity.principalId -o tsv)

# Grant Key Vault Secrets User to the VM identity
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee $VM_IDENTITY \
  --scope $(az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)

echo "VM identity $VM_IDENTITY granted Key Vault Secrets User"
```

### 6A.3 — SSH to VM and install Docker

```bash
ssh azureuser@$VM_IP

# On the VM:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az version
```

### 6A.4 — Pull secrets from Key Vault on the VM

```bash
# On the VM — these use the Managed Identity (no credentials needed):
az login --identity

KV_NAME="kv-diiac-vendorlogic"

ADMIN_TOKEN=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-admin-api-token" --query "value" -o tsv)
SIGNING_KEY=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-signing-private-key-pem" --query "value" -o tsv)
OPENAI_KEY=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-openai-api-key" --query "value" -o tsv)
API_SECRET=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-entra-client-secret" --query "value" -o tsv)

echo "Secrets retrieved from Key Vault ✓"
```

### 6A.5 — Clone repository and configure

```bash
# On the VM:
git clone https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git diiac
cd diiac
git checkout v1.2.0

# Write .env from Key Vault secrets
# (Replace the ENTRA_ values with your actual app IDs from Step 5)
cat > .env <<ENVEOF
# DIIaC v1.2.0 — Vendorlogic Production
APP_ENV=production
ADMIN_AUTH_ENABLED=true
STRICT_DETERMINISTIC_MODE=true

ADMIN_API_TOKEN=${ADMIN_TOKEN}
SIGNING_PRIVATE_KEY_PEM=${SIGNING_KEY}

LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_MODEL=gpt-4o-mini

# Entra ID — bridge auth
AUTH_MODE=entra_jwt_rs256
ENTRA_TENANT_ID=YOUR_TENANT_ID
ENTRA_CLIENT_ID=YOUR_API_APP_ID
ENTRA_CLIENT_SECRET=${API_SECRET}
ENTRA_AUDIENCE=api://YOUR_API_APP_ID
ENTRA_ISSUER=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0

# Port config
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173
ENVEOF

# Bridge .env (separate file read by Node.js)
cat > backend-ui-bridge/.env <<BRIDGEEOF
PYTHON_BASE_URL=http://governance-runtime:8000
LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_MODEL=gpt-4o-mini
AUTH_MODE=entra_jwt_rs256
ENTRA_TENANT_ID=YOUR_TENANT_ID
ENTRA_CLIENT_ID=YOUR_API_APP_ID
ENTRA_CLIENT_SECRET=${API_SECRET}
ENTRA_AUDIENCE=api://YOUR_API_APP_ID
ENTRA_ISSUER=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
BRIDGEEOF

# Frontend .env (Vite)
cat > Frontend/.env <<FEEOF
VITE_API_BASE=http://localhost:3001
VITE_ENTRA_CLIENT_ID=YOUR_UI_APP_ID
VITE_ENTRA_TENANT_ID=YOUR_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173
VITE_ENTRA_GROUP_MAP={"YOUR_ADMIN_GROUP_ID":"admin","YOUR_USER_GROUP_ID":"standard"}
FEEOF
```

### 6A.6 — Start the full stack

```bash
# On the VM — in the diiac directory:
docker compose up -d

# Watch startup
docker compose logs -f

# Wait for all 3 services to be healthy (about 60 seconds):
docker compose ps

# Verify runtime health
curl http://localhost:8000/health

# Verify admin auth is enforced
curl http://localhost:8000/admin/health
# Should return 401 — correct

# Verify with token
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/health
# Should return {"status":"OK",...}
```

### 6A.7 — Run production readiness checks

```bash
# On the VM:
pip3 install requests 2>/dev/null || pip install requests
python3 scripts_production_readiness_check.py

# All checks must pass. If any fail, check:
#   docker compose logs governance-runtime
```

**You are live.** Access the UI at `http://<VM_IP>:5173`

---

## Step 6B — Option B: Azure Kubernetes Service (Production)

Best for: multi-user, production SLA, HA, autoscaling.

### 6B.1 — Create AKS cluster

```bash
# Create AKS with Azure Key Vault Secrets Store CSI Driver enabled
az aks create \
  --resource-group $RG \
  --name "aks-diiac-prod" \
  --node-count 2 \
  --node-vm-size Standard_D2s_v3 \
  --enable-addons azure-keyvault-secrets-provider \
  --enable-managed-identity \
  --generate-ssh-keys \
  --kubernetes-version 1.29 \
  --output table

# Get credentials
az aks get-credentials --resource-group $RG --name "aks-diiac-prod"

# Verify
kubectl get nodes
```

### 6B.2 — Grant AKS identity access to Key Vault

```bash
# Get the AKS managed identity
AKS_IDENTITY=$(az aks show \
  --resource-group $RG \
  --name "aks-diiac-prod" \
  --query addonProfiles.azureKeyvaultSecretsProvider.identity.objectId \
  -o tsv)

# Grant Key Vault Secrets User
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee $AKS_IDENTITY \
  --scope $(az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)

echo "AKS identity $AKS_IDENTITY granted Key Vault Secrets User"
```

### 6B.3 — Create SecretProviderClass

Create the Azure Key Vault CSI driver config that maps Key Vault secrets to
Kubernetes secrets:

```bash
KV_TENANT_ID=$(az keyvault show --name $KV_NAME --query properties.tenantId -o tsv)
KV_RESOURCE_ID=$(az keyvault show --name $KV_NAME --query id -o tsv)

kubectl apply -n diiac -f - <<EOYAML
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: diiac-keyvault-secrets
  namespace: diiac
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    userAssignedIdentityID: ""
    keyvaultName: "${KV_NAME}"
    tenantId: "${KV_TENANT_ID}"
    objects: |
      array:
        - |
          objectName: diiac-admin-api-token
          objectType: secret
          objectAlias: ADMIN_API_TOKEN
        - |
          objectName: diiac-signing-private-key-pem
          objectType: secret
          objectAlias: SIGNING_PRIVATE_KEY_PEM
        - |
          objectName: diiac-openai-api-key
          objectType: secret
          objectAlias: OPENAI_API_KEY
        - |
          objectName: diiac-entra-client-secret
          objectType: secret
          objectAlias: ENTRA_CLIENT_SECRET
  secretObjects:
    - secretName: diiac-secrets
      type: Opaque
      data:
        - objectName: ADMIN_API_TOKEN
          key: ADMIN_API_TOKEN
        - objectName: SIGNING_PRIVATE_KEY_PEM
          key: SIGNING_PRIVATE_KEY_PEM
        - objectName: OPENAI_API_KEY
          key: OPENAI_API_KEY
        - objectName: ENTRA_CLIENT_SECRET
          key: ENTRA_CLIENT_SECRET
EOYAML
```

### 6B.4 — Deploy to Kubernetes

```bash
# Apply all manifests in order
kubectl apply -f deploy/kubernetes/namespace.yaml
kubectl apply -f deploy/kubernetes/persistent-volumes.yaml

# Apply SecretProviderClass (CSI populates diiac-secrets automatically)
# The governance-runtime pod must mount the CSI volume to trigger secret sync.
# (The deployment YAML references diiac-secrets which CSI creates on first mount.)

kubectl apply -f deploy/kubernetes/governance-runtime.yaml
kubectl apply -f deploy/kubernetes/backend-ui-bridge.yaml
kubectl apply -f deploy/kubernetes/frontend.yaml
kubectl apply -f deploy/kubernetes/ingress.yaml

# Watch deployment
kubectl get pods -n diiac -w

# Verify health
kubectl exec -n diiac deployment/governance-runtime -- \
  wget -qO- http://localhost:8000/health

# Check admin auth
kubectl exec -n diiac deployment/governance-runtime -- \
  wget -qO- --header "Authorization: Bearer $(kubectl get secret diiac-secrets -n diiac -o jsonpath='{.data.ADMIN_API_TOKEN}' | base64 -d)" \
  http://localhost:8000/admin/health
```

### 6B.5 — Configure Ingress with TLS

```bash
# Install cert-manager for automatic Let's Encrypt TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=120s

# Create Let's Encrypt ClusterIssuer
kubectl apply -f - <<EOYAML
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@vendorlogic.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
EOYAML

# Update ingress.yaml: uncomment the tls block and set your domain, then:
kubectl apply -f deploy/kubernetes/ingress.yaml
```

---

## Step 7 — Validate the Deployment

Run these validation steps regardless of which deployment option you chose.

### 7.1 — Admin health check

```bash
RUNTIME_URL="http://localhost:8000"   # or your ingress URL

# Health (no auth required)
curl -s $RUNTIME_URL/health | python3 -m json.tool

# Admin health (requires token)
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  $RUNTIME_URL/admin/health | python3 -m json.tool

# Expected: "status": "OK", "signing_enabled": true, "key_mode": "configured"
```

### 7.2 — Load business profiles

```bash
curl -s $RUNTIME_URL/api/business-profiles | python3 -m json.tool
# Expected: 8 sector profiles listed
```

### 7.3 — First governed compile — IT Enterprise scenario

```bash
CONTEXT_ID="vendorlogic-test-$(date +%s)"

# Step 1: Ingest role input (CTO)
curl -s -X POST $RUNTIME_URL/api/human-input/role \
  -H "Content-Type: application/json" \
  -d "{
    \"execution_context_id\": \"$CONTEXT_ID\",
    \"role\": \"CTO\",
    \"domain\": \"Cloud Infrastructure Procurement\",
    \"assertions\": [
      \"Multi-cloud strategy with Azure primary\",
      \"Zero-trust security posture required\",
      \"UK data residency mandatory\"
    ],
    \"non_negotiables\": [
      \"Microsoft Entra ID integration\",
      \"ISO 27001 compliance\",
      \"99.9% uptime SLA\"
    ],
    \"risk_flags\": [
      \"Single-vendor lock-in\",
      \"Shadow IT proliferation\"
    ],
    \"evidence_refs\": [
      \"REF-001: Board technology mandate Q1 2026\",
      \"REF-002: CISO risk register 2026\"
    ]
  }" | python3 -m json.tool

# Step 2: Governed compile
COMPILE_RESULT=$(curl -s -X POST $RUNTIME_URL/api/governed-compile \
  -H "Content-Type: application/json" \
  -d "{
    \"execution_context_id\": \"$CONTEXT_ID\",
    \"schema_id\": \"it_enterprise_governance_v1\",
    \"profile_id\": \"it_enterprise\",
    \"reasoning_level\": \"strategic\",
    \"policy_level\": \"board\",
    \"governance_modes\": [\"strict\", \"hitl\"]
  }")

echo $COMPILE_RESULT | python3 -m json.tool

EXEC_ID=$(echo $COMPILE_RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")
echo "Execution ID: $EXEC_ID"
```

### 7.4 — Verify the output

```bash
# Verify against trust ledger
curl -s $RUNTIME_URL/verify/execution/$EXEC_ID | python3 -m json.tool
# Expected: "status": "VERIFIABLE", "ledger_match": true

# Get Merkle tree
curl -s $RUNTIME_URL/executions/$EXEC_ID/merkle | python3 -m json.tool

# Get vendor scoring
curl -s $RUNTIME_URL/executions/$EXEC_ID/scoring | python3 -m json.tool

# Export signed decision pack
curl -s $RUNTIME_URL/decision-pack/$EXEC_ID/export-signed | python3 -m json.tool
# Expected: signature_alg: Ed25519, signing_key_id: non-empty
```

### 7.5 — Admin audit export

```bash
curl -s -X POST $RUNTIME_URL/admin/audit-export \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"execution_ids\": [\"$EXEC_ID\"]}" | python3 -m json.tool
# Expected: 201 with audit_export_id and download_url
```

### 7.6 — Trust ledger status

```bash
curl -s $RUNTIME_URL/trust/status | python3 -m json.tool
# ledger_records should be > 0
```

### 7.7 — Admin metrics

```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  $RUNTIME_URL/admin/metrics | python3 -m json.tool
# health_status: OK, alerts: []
```

---

## Step 8 — Entra ID RBAC Mapping

Configure the bridge `VITE_ENTRA_GROUP_MAP` and bridge `AUTH_MODE` to map
your Entra ID group IDs to DIIaC roles.

| Entra Group | DIIaC Role | Permissions |
|-------------|-----------|-------------|
| `DIIaC-Admins` | `admin` | All endpoints including `/admin/*` |
| `DIIaC-Users` | `standard` | Governance compile, verify, trust endpoints |
| (default) | `customer` | Read-only profile and health endpoints |

### Group ID lookup

```bash
az ad group show --group "DIIaC-Admins" --query id -o tsv
az ad group show --group "DIIaC-Users" --query id -o tsv
```

### Update bridge .env or K8s ConfigMap

```
ENTRA_GROUP_ADMIN=<DIIaC-Admins group ID>
ENTRA_GROUP_STANDARD=<DIIaC-Users group ID>
```

Or in the Vite frontend `.env`:
```
VITE_ENTRA_GROUP_MAP={"<admin-group-id>":"admin","<user-group-id>":"standard"}
```

---

## Step 9 — Secret Rotation Procedures

### Admin API Token rotation

```bash
# Generate new token
NEW_TOKEN=$(openssl rand -hex 32)

# Update Key Vault
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-admin-api-token" \
  --value "$NEW_TOKEN"

# For Docker Compose — update .env and restart bridge:
docker compose restart backend-ui-bridge governance-runtime

# For Kubernetes — update secret and rolling-restart:
kubectl patch secret diiac-secrets -n diiac \
  --type='json' \
  -p="[{\"op\":\"replace\",\"path\":\"/data/ADMIN_API_TOKEN\",\"value\":\"$(echo -n $NEW_TOKEN | base64)\"}]"
kubectl rollout restart deployment/governance-runtime -n diiac
```

### Signing key rotation (plan carefully)

> **Warning:** Rotating the signing key means existing signatures cannot be
> verified with the new key. Perform a full audit export before rotating.

```bash
# 1. Export all current executions
curl -s -X POST $RUNTIME_URL/admin/audit-export \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" | python3 -m json.tool

# 2. Generate new key
openssl genpkey -algorithm ed25519 -out diiac_signing_key_new.pem

# 3. Store in Key Vault (old version is retained by soft-delete)
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-signing-private-key-pem" \
  --file diiac_signing_key_new.pem

# 4. Restart runtime to load new key
docker compose restart governance-runtime
# or: kubectl rollout restart deployment/governance-runtime -n diiac

# 5. Update public_keys.json with the new public key
openssl pkey -in diiac_signing_key_new.pem -pubout
# Add the new public key to contracts/keys/public_keys.json
```

### OpenAI API Key rotation

```bash
# Obtain new key from https://platform.openai.com/api-keys
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "diiac-openai-api-key" \
  --value "sk-new-key-here"

# Restart bridge (which makes the LLM calls)
docker compose restart backend-ui-bridge
# or: kubectl rollout restart deployment/backend-ui-bridge -n diiac
```

---

## Step 10 — Monitoring Setup

### 10a — Azure Monitor integration (recommended for Vendorlogic)

```bash
# Create Log Analytics workspace
az monitor log-analytics workspace create \
  --resource-group $RG \
  --workspace-name "law-diiac-prod" \
  --location $LOCATION

# Get workspace ID
LAW_ID=$(az monitor log-analytics workspace show \
  --resource-group $RG \
  --workspace-name "law-diiac-prod" \
  --query id -o tsv)

# For AKS: enable Container Insights
az aks enable-addons \
  --addons monitoring \
  --name "aks-diiac-prod" \
  --resource-group $RG \
  --workspace-resource-id $LAW_ID
```

### 10b — Prometheus (standalone)

```bash
# Docker Compose — add Prometheus sidecar:
docker run -d \
  --name diiac-prometheus \
  --network diiac_v120_default \
  -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml \
  prom/prometheus:latest

# Access Prometheus: http://localhost:9090
```

### 10c — Key alerts to configure

| Alert | Trigger | Action |
|-------|---------|--------|
| `DIIaC_RuntimeDown` | `/health` unreachable | Page on-call, auto-restart |
| `DIIaC_NoSignedExecutions` | MTR-001 | Check signing key, restart runtime |
| `DIIaC_LedgerEmpty` | MTR-002 | Investigate audit trail integrity |
| `DIIaC_StorageNearFull` | PVC >85% | Extend PVC or archive exports |

---

## Step 11 — Production Hardening Checklist

Before going live with real Vendorlogic governance decisions:

- [ ] `APP_ENV=production` confirmed in `/admin/health` response
- [ ] `ADMIN_AUTH_ENABLED=true` confirmed in `/admin/health`
- [ ] `signing_enabled: true` and `key_mode: configured` in `/admin/health`
- [ ] All secrets sourced from Key Vault (no plaintext in .env or K8s manifests)
- [ ] VM/AKS MSI granted only "Key Vault Secrets User" (not Secrets Officer)
- [ ] Network Security Group: port 8000 NOT open to public internet
- [ ] TLS enabled at load balancer / ingress layer
- [ ] Admin token rotated after initial setup
- [ ] `pytest` all 21 tests passing in production config
- [ ] `scripts_production_readiness_check.py` all checks passing
- [ ] Audit export tested and download URL verified
- [ ] Entra group → RBAC role mapping tested with real user login
- [ ] Key Vault soft-delete and purge protection enabled
- [ ] Azure Monitor / Prometheus alerts configured and tested
- [ ] Signing key backup stored in a second Key Vault or offline HSM
- [ ] Incident response runbook shared with Vendorlogic security team

---

## Troubleshooting

### "admin_auth_required" on /admin/* endpoints

```bash
# Confirm token is correct
echo $ADMIN_TOKEN | wc -c   # Should be 65 (64 hex chars + newline)

# Confirm runtime has the token
docker compose exec governance-runtime env | grep ADMIN_API_TOKEN
```

### "signing_enabled: false" or "key_mode: ephemeral"

```bash
# Key not loaded — check PEM format
docker compose exec governance-runtime env | grep SIGNING_PRIVATE_KEY_PEM | head -c 100

# PEM must start with: -----BEGIN PRIVATE KEY-----
# If sourced from Key Vault, verify no extra whitespace:
az keyvault secret show --vault-name $KV_NAME --name "diiac-signing-private-key-pem" \
  --query "value" -o tsv | head -1
```

### "overall_ready: false" on /health

```bash
# Check which readiness check is failing
curl -s http://localhost:8000/health | python3 -c \
  "import sys,json; r=json.load(sys.stdin)['readiness']; [print(k,v) for k,v in r.items()]"

# Common cause: contracts directory not found
docker compose exec governance-runtime ls /app/contracts/business-profiles/
```

### Docker Compose: port conflict

```bash
# Use override vars in .env:
RUNTIME_HOST_PORT=8001
BRIDGE_HOST_PORT=3002
FRONTEND_HOST_PORT=5174
```

### Entra ID 401 on bridge endpoints

```bash
# Verify AUTH_MODE and ENTRA_ vars in bridge .env
docker compose exec backend-ui-bridge env | grep ENTRA
docker compose exec backend-ui-bridge env | grep AUTH_MODE

# Test token with bridge health
curl -s http://localhost:3001/health
# Should return 200 with bridge status
```

---

## Reference

| What | Where |
|------|-------|
| API spec | `openapi.yaml` — all 30+ endpoints |
| Security policy | `SECURITY.md` |
| Deployment validation | `DEPLOYMENT_VALIDATION_RUNBOOK.md` |
| Offline verification | `OFFLINE_VERIFIER_RUNBOOK.md` |
| UI workflow guide | `DIIAC_UI_WORKFLOW_GUIDE.md` |
| Admin console guide | `ADMIN_CONSOLE_USER_GUIDE.md` |
| Entra ID setup | `ENTRA_ID_SETUP_GUIDE.md` |
| 84-point Entra checklist | `COPILOT_ENTRA_PRODUCTION_CHECKLIST.md` |
| Key Vault documentation | https://learn.microsoft.com/azure/key-vault/ |
| AKS CSI driver docs | https://learn.microsoft.com/azure/aks/csi-secrets-store-driver |
| cert-manager docs | https://cert-manager.io/docs/ |
