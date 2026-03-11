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
- **Azure Container Instances (ACI)** — Automated Bicep landing zone (fastest production path)
- **Docker Compose on Azure VM** — Fastest path for initial validation

**Estimated time to first governed compile:** ~30 minutes (ACI Bicep) / ~90 minutes (VM path) / ~3 hours (AKS path)

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

```powershell
# Azure CLI (via MSI installer or winget)
winget install Microsoft.AzureCLI
az version

# Docker Desktop (for VM path — install from https://www.docker.com/products/docker-desktop/)
docker compose version

# kubectl + helm (for AKS path)
az aks install-cli
helm version

# OpenSSL (ships with Git for Windows, or install via winget)
openssl version
```

### Azure requirements

- Azure subscription with Contributor access
- Permission to create App Registrations in Entra ID
- Permission to create and configure Key Vaults

---

## Step 1 — Azure Login and Setup

```powershell
# Login
az login

# Set your subscription
az account set --subscription "YOUR-SUBSCRIPTION-NAME-OR-ID"
az account show

# Set variables for this deployment (edit these)
$RG = "rg-diiac-prod"
$LOCATION = "uksouth"
$KV_NAME = "kv-diiac-vendorlogic"
$APP_NAME = "diiac-vendorlogic"
$TENANT_ID = (az account show --query tenantId -o tsv)

Write-Host "Tenant ID: $TENANT_ID"
Write-Host "Resource Group: $RG"
Write-Host "Key Vault: $KV_NAME"
```

---

## Step 2 — Create Resource Group and Key Vault

```powershell
# Create resource group
az group create --name $RG --location $LOCATION

# Create Key Vault (soft-delete enabled, RBAC authorisation model)
az keyvault create `
  --name $KV_NAME `
  --resource-group $RG `
  --location $LOCATION `
  --sku standard `
  --enable-rbac-authorization true `
  --retention-days 90

# Grant yourself Key Vault Secrets Officer (to populate secrets)
$MY_OBJECT_ID = (az ad signed-in-user show --query id -o tsv)

$KV_SCOPE = (az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)
az role assignment create `
  --role "Key Vault Secrets Officer" `
  --assignee $MY_OBJECT_ID `
  --scope $KV_SCOPE

Write-Host "Key Vault created: $KV_NAME"
```

---

## Step 3 — Generate Secrets

### 3a — Admin API Token

```powershell
# Generate a cryptographically random 32-byte hex token
$ADMIN_TOKEN = (openssl rand -hex 32)
Write-Host "Admin token (save this securely): $ADMIN_TOKEN"
```

### 3b — Ed25519 Signing Key

```powershell
# Generate Ed25519 private key in PKCS8 PEM format
openssl genpkey -algorithm ed25519 -out diiac_signing_key.pem
Get-Content diiac_signing_key.pem

# Extract public key (keep for offline verification)
openssl pkey -in diiac_signing_key.pem -pubout -out diiac_signing_key_pub.pem
Get-Content diiac_signing_key_pub.pem

# IMPORTANT: Back up diiac_signing_key.pem securely.
# Loss of this key means existing signatures cannot be verified.
```

### 3c — OpenAI API Key

Obtain from: https://platform.openai.com/api-keys

```powershell
$OPENAI_KEY = "sk-..."   # Your key from OpenAI platform
```

---

## Step 4 — Populate Key Vault

```powershell
# Store Admin API Token
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-admin-api-token" `
  --value "$ADMIN_TOKEN"

# Store Ed25519 Signing Key (PEM with newlines preserved)
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-signing-private-key-pem" `
  --file diiac_signing_key.pem

# Store OpenAI API Key
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-openai-api-key" `
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

```powershell
# Create the API app registration
$API_APP = (az ad app create `
  --display-name "DIIaC-API-Vendorlogic" `
  --query "appId" -o tsv)

Write-Host "API App ID (client_id): $API_APP"

# Create a service principal for the app
az ad sp create --id $API_APP

# Create a client secret for the bridge to validate tokens with
$API_SECRET = (az ad app credential reset `
  --id $API_APP `
  --display-name "diiac-bridge-secret" `
  --query "password" -o tsv)

Write-Host "API client secret (store in Key Vault): $API_SECRET"

# Store in Key Vault
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-entra-client-secret" `
  --value "$API_SECRET"

# Expose an API scope for the frontend to call
az ad app update `
  --id $API_APP `
  --identifier-uris "api://$API_APP"

# Add a scope: access_as_user
$APP_OBJECT_ID = (az ad app show --id $API_APP --query id -o tsv)
$SCOPE_ID = [guid]::NewGuid().ToString()

az rest --method POST `
  --uri "https://graph.microsoft.com/v1.0/applications/$APP_OBJECT_ID/api/oauth2PermissionScopes" `
  --body (@{
    adminConsentDescription = "Access DIIaC as a user"
    adminConsentDisplayName = "Access DIIaC"
    id                      = $SCOPE_ID
    isEnabled               = $true
    type                    = "User"
    userConsentDescription  = "Allow this app to access DIIaC on your behalf"
    userConsentDisplayName  = "Access DIIaC"
    value                   = "access_as_user"
  } | ConvertTo-Json -Compress)

Write-Host "DIIaC-API app: $API_APP"
Write-Host "Tenant ID: $TENANT_ID"
```

### 5b — DIIaC-UI registration (frontend MSAL)

```powershell
# Create the frontend app registration
$UI_APP = (az ad app create `
  --display-name "DIIaC-UI-Vendorlogic" `
  --query "appId" -o tsv)

Write-Host "UI App ID: $UI_APP"

# Create service principal
az ad sp create --id $UI_APP

# Set redirect URIs (SPA platform — required for MSAL v5 Auth Code + PKCE)
az ad app update `
  --id $UI_APP `
  --spa-redirect-uris "http://localhost:5173/auth/callback" "http://localhost:5173" "https://diiac.vendorlogic.com"

# Grant admin consent for the API scope
# (Tenant admin must run this, or grant via Azure Portal)
$UI_SP_ID = (az ad sp show --id $UI_APP --query id -o tsv)
$API_SP_ID = (az ad sp show --id $API_APP --query id -o tsv)

az rest --method POST `
  --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" `
  --body (@{
    clientId    = $UI_SP_ID
    consentType = "AllPrincipals"
    resourceId  = $API_SP_ID
    scope       = "access_as_user"
  } | ConvertTo-Json -Compress)

Write-Host "DIIaC-UI app: $UI_APP"
```

### 5c — Create Entra ID Groups for RBAC

```powershell
# Create admin group
$ADMIN_GROUP = (az ad group create `
  --display-name "DIIaC-Admins" `
  --mail-nickname "DIIaC-Admins" `
  --query "id" -o tsv)

# Create standard user group
$USER_GROUP = (az ad group create `
  --display-name "DIIaC-Users" `
  --mail-nickname "DIIaC-Users" `
  --query "id" -o tsv)

Write-Host "Admin Group ID:  $ADMIN_GROUP"
Write-Host "User Group ID:   $USER_GROUP"

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

## Step 6-ACI — Option ACI: Bicep Landing Zone (Recommended — ~30 min)

Best for: production customer testing with full IaC, automated infrastructure, no manual VM management.

This option uses the Bicep template in `infra/main.bicep` to provision all Azure resources
(ACR, ACI, Key Vault, Storage, Managed Identity, Log Analytics) in a single deployment,
then builds and pushes container images to ACR automatically.

### Prerequisites

- Key Vault secrets populated (Steps 3–4 above)
- Entra app registrations created (Step 5 above)
- Docker running locally

### 6-ACI.1 — One-command deployment

```powershell
& scripts/deploy-azure.ps1 -Customer vendorlogic
```

> **Note:** If only `scripts/deploy-azure.sh` exists, run it from a WSL or Git Bash shell:
> `bash scripts/deploy-azure.sh --customer vendorlogic`

This script:
1. Deploys the Bicep landing zone (`infra/main.bicep` + `infra/main.bicepparam`)
2. Builds all 3 Docker images and pushes to the provisioned ACR
3. Pulls secrets from Key Vault
4. Creates the ACI container group with all secrets injected

### 6-ACI.2 — What gets provisioned

| Resource | Name | Purpose |
|----------|------|---------|
| Container Registry | `acrdiiac<unique>` | Private Docker image store |
| Key Vault | `kv-diiac-vendorlogic` | Secrets (admin token, signing key, API keys) |
| Storage Account | `stdiiac<unique>` | Persistent file shares (6 shares) |
| Container Group | `aci-diiac-vendorlogic` | 3-container group (runtime + bridge + frontend) |
| Managed Identity | `id-diiac-vendorlogic` | ACR Pull + KV Secrets User (zero credentials) |
| Log Analytics | `law-diiac-vendorlogic` | Container logs, 90-day retention |

### 6-ACI.3 — Update Entra redirect URI

After deployment, update the redirect URI to match the ACI FQDN:

```
https://diiac-vendorlogic.uksouth.azurecontainer.io/auth/callback
```

Update in Entra portal → App registrations → `DIIaC-UI-Vendorlogic` → Authentication → Redirect URIs.

### 6-ACI.4 — Verify

```powershell
# Health check
Invoke-RestMethod -Uri "https://diiac-vendorlogic.uksouth.azurecontainer.io/health"

# Container logs
az container logs -g rg-diiac-prod -n aci-diiac-vendorlogic --container-name governance-runtime
az container logs -g rg-diiac-prod -n aci-diiac-vendorlogic --container-name backend-ui-bridge
```

### 6-ACI.5 — Redeployment (code updates only)

```powershell
# Rebuild images and restart ACI (infrastructure unchanged)
& scripts/deploy-azure.ps1 -Customer vendorlogic -SkipInfra
```

> **Note:** If only the bash script exists:
> `bash scripts/deploy-azure.sh --customer vendorlogic --skip-infra`

### 6-ACI.6 — Tear down

```powershell
az group delete --name rg-diiac-prod --yes --no-wait
```

---

## Step 6A — Option A: Docker Compose on Azure VM (Fastest — ~90 min)

Best for: initial validation, development, low-traffic internal use.

### 6A.1 — Create Azure VM

```powershell
$VM_NAME = "vm-diiac-prod"
$VM_SIZE = "Standard_B2s"   # 2 vCPU, 4GB RAM — sufficient for DIIaC

az vm create `
  --resource-group $RG `
  --name $VM_NAME `
  --image Ubuntu2204 `
  --size $VM_SIZE `
  --admin-username azureuser `
  --generate-ssh-keys `
  --assign-identity `
  --public-ip-sku Standard `
  --output table

# Open ports
az vm open-port --resource-group $RG --name $VM_NAME --port 443 --priority 1001
az vm open-port --resource-group $RG --name $VM_NAME --port 80 --priority 1002

# Get public IP
$VM_IP = (az vm show --resource-group $RG --name $VM_NAME -d --query publicIps -o tsv)
Write-Host "VM IP: $VM_IP"
```

### 6A.2 — Grant VM Managed Identity access to Key Vault

```powershell
# Get the VM's managed identity principal ID
$VM_IDENTITY = (az vm show `
  --resource-group $RG `
  --name $VM_NAME `
  --query identity.principalId -o tsv)

# Grant Key Vault Secrets User to the VM identity
$KV_SCOPE = (az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $VM_IDENTITY `
  --scope $KV_SCOPE

Write-Host "VM identity $VM_IDENTITY granted Key Vault Secrets User"
```

### 6A.3 — SSH to VM and install Docker

```powershell
ssh azureuser@$VM_IP

# On the VM (bash commands — this is a Linux VM):
# curl -fsSL https://get.docker.com | sh
# sudo usermod -aG docker $USER
# newgrp docker
#
# # Install Azure CLI
# curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
# az version
```

### 6A.4 — Pull secrets from Key Vault on the VM

```powershell
# On the VM (bash) — these use the Managed Identity (no credentials needed):
# az login --identity
#
# KV_NAME="kv-diiac-vendorlogic"
#
# ADMIN_TOKEN=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-admin-api-token" --query "value" -o tsv)
# SIGNING_KEY=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-signing-private-key-pem" --query "value" -o tsv)
# OPENAI_KEY=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-openai-api-key" --query "value" -o tsv)
# API_SECRET=$(az keyvault secret show --vault-name $KV_NAME --name "diiac-entra-client-secret" --query "value" -o tsv)

# Alternatively, pull secrets from your local PowerShell session:
$ADMIN_TOKEN = (az keyvault secret show --vault-name $KV_NAME --name "diiac-admin-api-token" --query "value" -o tsv)
$SIGNING_KEY = (az keyvault secret show --vault-name $KV_NAME --name "diiac-signing-private-key-pem" --query "value" -o tsv)
$OPENAI_KEY = (az keyvault secret show --vault-name $KV_NAME --name "diiac-openai-api-key" --query "value" -o tsv)
$API_SECRET = (az keyvault secret show --vault-name $KV_NAME --name "diiac-entra-client-secret" --query "value" -o tsv)

Write-Host "Secrets retrieved from Key Vault"
```

### 6A.5 — Clone repository and configure

```powershell
# On the VM (bash — Linux VM):
# git clone https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git diiac
# cd diiac
# git checkout v1.2.0

# Generate .env files from your local PowerShell, then SCP them to the VM:

# Root .env (Replace YOUR_ placeholders with actual values from Step 5)
@"
# DIIaC v1.2.0 — Vendorlogic Production
APP_ENV=production
ADMIN_AUTH_ENABLED=true
STRICT_DETERMINISTIC_MODE=true

ADMIN_API_TOKEN=$ADMIN_TOKEN
SIGNING_PRIVATE_KEY_PEM=$SIGNING_KEY

LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-4o-mini

# Entra ID — bridge auth
AUTH_MODE=entra_jwt_rs256
ENTRA_TENANT_ID=YOUR_TENANT_ID
ENTRA_CLIENT_ID=YOUR_API_APP_ID
ENTRA_CLIENT_SECRET=$API_SECRET
ENTRA_AUDIENCE=api://YOUR_API_APP_ID
ENTRA_ISSUER=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0

# Port config
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173
"@ | Set-Content -Path ".env" -Encoding UTF8

# Bridge .env
@"
PYTHON_BASE_URL=http://governance-runtime:8000
LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-4o-mini
AUTH_MODE=entra_jwt_rs256
ENTRA_TENANT_ID=YOUR_TENANT_ID
ENTRA_CLIENT_ID=YOUR_API_APP_ID
ENTRA_CLIENT_SECRET=$API_SECRET
ENTRA_AUDIENCE=api://YOUR_API_APP_ID
ENTRA_ISSUER=https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0
"@ | Set-Content -Path "backend-ui-bridge/.env" -Encoding UTF8

# Frontend .env
@"
VITE_API_BASE=http://localhost:3001
VITE_ENTRA_CLIENT_ID=YOUR_UI_APP_ID
VITE_ENTRA_TENANT_ID=YOUR_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173
VITE_ENTRA_GROUP_MAP={"YOUR_ADMIN_GROUP_ID":"admin","YOUR_USER_GROUP_ID":"standard"}
"@ | Set-Content -Path "Frontend/.env" -Encoding UTF8

# SCP the .env files to the VM
scp .env azureuser@${VM_IP}:~/diiac/.env
scp backend-ui-bridge/.env azureuser@${VM_IP}:~/diiac/backend-ui-bridge/.env
scp Frontend/.env azureuser@${VM_IP}:~/diiac/Frontend/.env
```

### 6A.6 — Start the full stack

```powershell
# SSH to the VM and run (bash — Linux VM):
ssh azureuser@$VM_IP

# On the VM:
# cd diiac
# docker compose up -d
# docker compose logs -f
# docker compose ps

# Verify from your local PowerShell:
Invoke-RestMethod -Uri "http://${VM_IP}:8000/health"

# Verify admin auth is enforced (should return 401)
try {
    Invoke-RestMethod -Uri "http://${VM_IP}:8000/admin/health"
} catch {
    Write-Host "Got 401 — admin auth enforced correctly"
}

# Verify with token
$headers = @{ Authorization = "Bearer $ADMIN_TOKEN" }
Invoke-RestMethod -Uri "http://${VM_IP}:8000/admin/health" -Headers $headers
# Should return status: OK
```

### 6A.7 — Run production readiness checks

```powershell
# SSH to the VM:
ssh azureuser@$VM_IP

# On the VM:
# pip3 install requests 2>/dev/null || pip install requests
# python3 scripts_production_readiness_check.py

# All checks must pass. If any fail, check:
#   docker compose logs governance-runtime
```

**You are live.** Access the UI at `http://<VM_IP>:5173`

---

## Step 6B — Option B: Azure Kubernetes Service (Production)

Best for: multi-user, production SLA, HA, autoscaling.

### 6B.1 — Create AKS cluster

```powershell
# Create AKS with Azure Key Vault Secrets Store CSI Driver enabled
az aks create `
  --resource-group $RG `
  --name "aks-diiac-prod" `
  --node-count 2 `
  --node-vm-size Standard_D2s_v3 `
  --enable-addons azure-keyvault-secrets-provider `
  --enable-managed-identity `
  --generate-ssh-keys `
  --kubernetes-version 1.29 `
  --output table

# Get credentials
az aks get-credentials --resource-group $RG --name "aks-diiac-prod"

# Verify
kubectl get nodes
```

### 6B.2 — Grant AKS identity access to Key Vault

```powershell
# Get the AKS managed identity
$AKS_IDENTITY = (az aks show `
  --resource-group $RG `
  --name "aks-diiac-prod" `
  --query addonProfiles.azureKeyvaultSecretsProvider.identity.objectId `
  -o tsv)

# Grant Key Vault Secrets User
$KV_SCOPE = (az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv)
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee $AKS_IDENTITY `
  --scope $KV_SCOPE

Write-Host "AKS identity $AKS_IDENTITY granted Key Vault Secrets User"
```

### 6B.3 — Create SecretProviderClass

Create the Azure Key Vault CSI driver config that maps Key Vault secrets to
Kubernetes secrets:

```powershell
$KV_TENANT_ID = (az keyvault show --name $KV_NAME --query properties.tenantId -o tsv)

$secretProviderYaml = @"
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
    keyvaultName: "$KV_NAME"
    tenantId: "$KV_TENANT_ID"
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
"@

$secretProviderYaml | kubectl apply -n diiac -f -
```

### 6B.4 — Deploy to Kubernetes

```powershell
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
kubectl exec -n diiac deployment/governance-runtime -- `
  wget -qO- http://localhost:8000/health

# Check admin auth
$ADMIN_TOKEN_B64 = (kubectl get secret diiac-secrets -n diiac -o jsonpath='{.data.ADMIN_API_TOKEN}')
$ADMIN_TOKEN_DECODED = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($ADMIN_TOKEN_B64))

kubectl exec -n diiac deployment/governance-runtime -- `
  wget -qO- --header "Authorization: Bearer $ADMIN_TOKEN_DECODED" `
  http://localhost:8000/admin/health
```

### 6B.5 — Configure Ingress with TLS

```powershell
# Install cert-manager for automatic Let's Encrypt TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=120s

# Create Let's Encrypt ClusterIssuer
$clusterIssuerYaml = @"
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
"@

$clusterIssuerYaml | kubectl apply -f -

# Update ingress.yaml: uncomment the tls block and set your domain, then:
kubectl apply -f deploy/kubernetes/ingress.yaml
```

---

## Step 7 — Validate the Deployment

Run these validation steps regardless of which deployment option you chose.

### 7.1 — Admin health check

```powershell
$RUNTIME_URL = "http://localhost:8000"   # or your ingress URL

# Health (no auth required)
Invoke-RestMethod -Uri "$RUNTIME_URL/health" | ConvertTo-Json -Depth 5

# Admin health (requires token)
$headers = @{ Authorization = "Bearer $ADMIN_TOKEN" }
Invoke-RestMethod -Uri "$RUNTIME_URL/admin/health" -Headers $headers | ConvertTo-Json -Depth 5

# Expected: "status": "OK", "signing_enabled": true, "key_mode": "configured"
```

### 7.2 — Load business profiles

```powershell
Invoke-RestMethod -Uri "$RUNTIME_URL/api/business-profiles" | ConvertTo-Json -Depth 5
# Expected: 8 sector profiles listed
```

### 7.3 — First governed compile — IT Enterprise scenario

```powershell
$CONTEXT_ID = "vendorlogic-test-$(Get-Date -Format 'yyyyMMddHHmmss')"

# Step 1: Ingest role input (CTO)
$roleBody = @{
    execution_context_id = $CONTEXT_ID
    role                 = "CTO"
    domain               = "Cloud Infrastructure Procurement"
    assertions           = @(
        "Multi-cloud strategy with Azure primary"
        "Zero-trust security posture required"
        "UK data residency mandatory"
    )
    non_negotiables      = @(
        "Microsoft Entra ID integration"
        "ISO 27001 compliance"
        "99.9% uptime SLA"
    )
    risk_flags           = @(
        "Single-vendor lock-in"
        "Shadow IT proliferation"
    )
    evidence_refs        = @(
        "REF-001: Board technology mandate Q1 2026"
        "REF-002: CISO risk register 2026"
    )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "$RUNTIME_URL/api/human-input/role" `
  -Method POST `
  -ContentType "application/json" `
  -Body $roleBody | ConvertTo-Json -Depth 5

# Step 2: Governed compile
$compileBody = @{
    execution_context_id = $CONTEXT_ID
    schema_id            = "it_enterprise_governance_v1"
    profile_id           = "it_enterprise"
    reasoning_level      = "strategic"
    policy_level         = "board"
    governance_modes     = @("strict", "hitl")
} | ConvertTo-Json -Depth 5

$COMPILE_RESULT = Invoke-RestMethod -Uri "$RUNTIME_URL/api/governed-compile" `
  -Method POST `
  -ContentType "application/json" `
  -Body $compileBody

$COMPILE_RESULT | ConvertTo-Json -Depth 5

$EXEC_ID = $COMPILE_RESULT.execution_id
Write-Host "Execution ID: $EXEC_ID"
```

### 7.4 — Verify the output

```powershell
# Verify against trust ledger
Invoke-RestMethod -Uri "$RUNTIME_URL/verify/execution/$EXEC_ID" | ConvertTo-Json -Depth 5
# Expected: "status": "VERIFIABLE", "ledger_match": true

# Get Merkle tree
Invoke-RestMethod -Uri "$RUNTIME_URL/executions/$EXEC_ID/merkle" | ConvertTo-Json -Depth 5

# Get vendor scoring
Invoke-RestMethod -Uri "$RUNTIME_URL/executions/$EXEC_ID/scoring" | ConvertTo-Json -Depth 5

# Export signed decision pack
Invoke-RestMethod -Uri "$RUNTIME_URL/decision-pack/$EXEC_ID/export-signed" | ConvertTo-Json -Depth 5
# Expected: signature_alg: Ed25519, signing_key_id: non-empty
```

### 7.5 — Admin audit export

```powershell
$auditBody = @{ execution_ids = @($EXEC_ID) } | ConvertTo-Json
$headers = @{
    Authorization  = "Bearer $ADMIN_TOKEN"
    "Content-Type" = "application/json"
}

Invoke-RestMethod -Uri "$RUNTIME_URL/admin/audit-export" `
  -Method POST `
  -Headers $headers `
  -Body $auditBody | ConvertTo-Json -Depth 5
# Expected: 201 with audit_export_id and download_url
```

### 7.6 — Trust ledger status

```powershell
Invoke-RestMethod -Uri "$RUNTIME_URL/trust/status" | ConvertTo-Json -Depth 5
# ledger_records should be > 0
```

### 7.7 — Admin metrics

```powershell
$headers = @{ Authorization = "Bearer $ADMIN_TOKEN" }
Invoke-RestMethod -Uri "$RUNTIME_URL/admin/metrics" -Headers $headers | ConvertTo-Json -Depth 5
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

```powershell
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

```powershell
# Generate new token
$NEW_TOKEN = (openssl rand -hex 32)

# Update Key Vault
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-admin-api-token" `
  --value "$NEW_TOKEN"

# For Docker Compose — update .env and restart bridge:
docker compose restart backend-ui-bridge governance-runtime

# For Kubernetes — update secret and rolling-restart:
$NEW_TOKEN_B64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($NEW_TOKEN))

kubectl patch secret diiac-secrets -n diiac `
  --type='json' `
  -p="[{`"op`":`"replace`",`"path`":`"/data/ADMIN_API_TOKEN`",`"value`":`"$NEW_TOKEN_B64`"}]"

kubectl rollout restart deployment/governance-runtime -n diiac
```

### Signing key rotation (plan carefully)

> **Warning:** Rotating the signing key means existing signatures cannot be
> verified with the new key. Perform a full audit export before rotating.

```powershell
# 1. Export all current executions
$headers = @{
    Authorization  = "Bearer $ADMIN_TOKEN"
    "Content-Type" = "application/json"
}
Invoke-RestMethod -Uri "$RUNTIME_URL/admin/audit-export" `
  -Method POST `
  -Headers $headers | ConvertTo-Json -Depth 5

# 2. Generate new key
openssl genpkey -algorithm ed25519 -out diiac_signing_key_new.pem

# 3. Store in Key Vault (old version is retained by soft-delete)
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-signing-private-key-pem" `
  --file diiac_signing_key_new.pem

# 4. Restart runtime to load new key
docker compose restart governance-runtime
# or: kubectl rollout restart deployment/governance-runtime -n diiac

# 5. Update public_keys.json with the new public key
openssl pkey -in diiac_signing_key_new.pem -pubout
# Add the new public key to contracts/keys/public_keys.json
```

### OpenAI API Key rotation

```powershell
# Obtain new key from https://platform.openai.com/api-keys
az keyvault secret set `
  --vault-name $KV_NAME `
  --name "diiac-openai-api-key" `
  --value "sk-new-key-here"

# Restart bridge (which makes the LLM calls)
docker compose restart backend-ui-bridge
# or: kubectl rollout restart deployment/backend-ui-bridge -n diiac
```

---

## Step 10 — Monitoring Setup

### 10a — Azure Monitor integration (recommended for Vendorlogic)

```powershell
# Create Log Analytics workspace
az monitor log-analytics workspace create `
  --resource-group $RG `
  --workspace-name "law-diiac-prod" `
  --location $LOCATION

# Get workspace ID
$LAW_ID = (az monitor log-analytics workspace show `
  --resource-group $RG `
  --workspace-name "law-diiac-prod" `
  --query id -o tsv)

# For AKS: enable Container Insights
az aks enable-addons `
  --addons monitoring `
  --name "aks-diiac-prod" `
  --resource-group $RG `
  --workspace-resource-id $LAW_ID
```

### 10b — Prometheus (standalone)

```powershell
# Docker Compose — add Prometheus sidecar:
docker run -d `
  --name diiac-prometheus `
  --network diiac_v120_default `
  -p 9090:9090 `
  -v "${PWD}/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml" `
  -v "${PWD}/monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml" `
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

```powershell
# Confirm token is correct
$ADMIN_TOKEN.Length   # Should be 64 (64 hex chars)

# Confirm runtime has the token
docker compose exec governance-runtime printenv ADMIN_API_TOKEN
```

### "signing_enabled: false" or "key_mode: ephemeral"

```powershell
# Key not loaded — check PEM format
$envVal = docker compose exec governance-runtime printenv SIGNING_PRIVATE_KEY_PEM
$envVal.Substring(0, [Math]::Min(100, $envVal.Length))

# PEM must start with: -----BEGIN PRIVATE KEY-----
# If sourced from Key Vault, verify no extra whitespace:
az keyvault secret show --vault-name $KV_NAME --name "diiac-signing-private-key-pem" `
  --query "value" -o tsv | Select-Object -First 1
```

### "overall_ready: false" on /health

```powershell
# Check which readiness check is failing
$health = Invoke-RestMethod -Uri "http://localhost:8000/health"
$health.readiness | Format-List

# Common cause: contracts directory not found
docker compose exec governance-runtime ls /app/contracts/business-profiles/
```

### Docker Compose: port conflict

```powershell
# Use override vars in .env:
# RUNTIME_HOST_PORT=8001
# BRIDGE_HOST_PORT=3002
# FRONTEND_HOST_PORT=5174
```

### Entra ID 401 on bridge endpoints

```powershell
# Verify AUTH_MODE and ENTRA_ vars in bridge .env
docker compose exec backend-ui-bridge printenv | Select-String "ENTRA"
docker compose exec backend-ui-bridge printenv AUTH_MODE

# Test token with bridge health
Invoke-RestMethod -Uri "http://localhost:3001/health"
# Should return 200 with bridge status
```

---

## Reference

| What | Where |
|------|-------|
| Bicep landing zone | `infra/main.bicep` — ACR, ACI, KV, Storage, Identity, Log Analytics |
| Bicep parameters | `infra/main.bicepparam` — Vendorlogic-specific values |
| Automated deploy script | `scripts/deploy-azure.sh` — build, push, deploy in one command |
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
