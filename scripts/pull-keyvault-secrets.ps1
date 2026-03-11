# DIIaC v1.2.0 - Pull secrets from Azure Key Vault for local Docker Desktop staging
# Windows PowerShell version
#
# Usage (from repository root):
#   .\scripts\pull-keyvault-secrets.ps1                          # defaults to vendorlogic
#   .\scripts\pull-keyvault-secrets.ps1 -Customer acmecorp       # use acmecorp config
#   $env:DIIAC_CUSTOMER = "acmecorp"; .\scripts\pull-keyvault-secrets.ps1  # env var alternative
#
# Prerequisites:
#   - Azure CLI installed (https://learn.microsoft.com/cli/azure/install-azure-cli-windows)
#   - az login completed
#   - Key Vault populated (see customer-config/<customer>/keyvault-secrets-manifest.md)
#
# Outputs:
#   .env                      - all non-PEM secrets for docker compose
#   .secrets\signing_key.pem  - Ed25519 signing key (bind-mounted by compose)

param(
    [string]$Customer = $env:DIIAC_CUSTOMER
)

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Customer selection ------------------------------------------------------
if (-not $Customer) { $Customer = "vendorlogic" }

# -- Configuration - loaded from customer config -----------------------------
# These are public identifiers (app registration IDs, group OIDs).
# Override any value by setting $env:VARIABLE before running this script.

$repoRoot    = Split-Path -Parent $PSScriptRoot
$configFile  = Join-Path (Join-Path (Join-Path $repoRoot "customer-config") $Customer) "config.env"
$configVars  = @{}

if (-not (Test-Path $configFile)) {
    Write-Host "Customer config not found: $configFile" -ForegroundColor Red
    Write-Host "  Create it by copying: customer-config\_template\config.env"
    Write-Host "  Then fill in the REPLACE_WITH_* placeholders for your customer."
    exit 1
}

Get-Content $configFile | Where-Object { $_ -match '^\s*[^#]\S+=\S*' } | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) { $configVars[$parts[0].Trim()] = $parts[1].Trim() }
}

function Cfg { param($key, $default) if ($configVars.ContainsKey($key)) { $configVars[$key] } else { $default } }

$KV_NAME              = if ($env:KEY_VAULT_NAME)        { $env:KEY_VAULT_NAME }        else { Cfg "KEY_VAULT_NAME"          "kv-diiac-vendorlogic" }
$ENTRA_TENANT_ID      = if ($env:AZURE_TENANT_ID)       { $env:AZURE_TENANT_ID }       else { Cfg "AZURE_TENANT_ID"         "1384b1c5-2bae-45a1-a4b4-e94e3315eb41" }
$ENTRA_API_APP_ID     = if ($env:ENTRA_API_APP_ID)      { $env:ENTRA_API_APP_ID }      else { Cfg "ENTRA_API_APP_ID"        "b726558d-f1c6-48f7-8a3d-72d5db818d0f" }
$ENTRA_UI_APP_ID      = if ($env:ENTRA_UI_APP_ID)       { $env:ENTRA_UI_APP_ID }       else { Cfg "ENTRA_UI_APP_ID"         "b726558d-f1c6-48f7-8a3d-72d5db818d0f" }
$ENTRA_ADMIN_GROUP_ID = if ($env:ENTRA_ADMIN_GROUP_ID)   { $env:ENTRA_ADMIN_GROUP_ID }   else { Cfg "ENTRA_ADMIN_GROUP_ID"  "81786818-de16-4115-b061-92fce74b00bd" }
$ENTRA_USER_GROUP_ID  = if ($env:ENTRA_STANDARD_GROUP_ID) { $env:ENTRA_STANDARD_GROUP_ID } else { Cfg "ENTRA_STANDARD_GROUP_ID" "9c7dd0d4-5b44-4811-b167-e52df21092d8" }

function Write-Ok   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "DIIaC v1.2.0 - Key Vault secret pull (Windows)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# -- Check az CLI --------------------------------------------------------------
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Fail "Azure CLI not found. Download from https://aka.ms/installazurecliwindows"
}

# -- Check login ---------------------------------------------------------------
$account = az account show --query "user.name" -o tsv 2>$null
if (-not $account) {
    Write-Warn "Not logged in to Azure CLI. Running az login..."
    az login
    $account = az account show --query "user.name" -o tsv
}
Write-Ok "Logged in as: $account"

# Auto-detect tenant if not set
if (-not $ENTRA_TENANT_ID) {
    $ENTRA_TENANT_ID = az account show --query tenantId -o tsv
    Write-Warn "ENTRA_TENANT_ID not set - using active tenant: $ENTRA_TENANT_ID"
}

# -- Check Key Vault -----------------------------------------------------------
$kvCheck = az keyvault show --name $KV_NAME --query name -o tsv 2>$null
if (-not $kvCheck) {
    Write-Fail "Key Vault '$KV_NAME' not found. Check KV_NAME or provision it first."
}
Write-Ok "Key Vault found: $KV_NAME"

# -- Create .secrets directory -------------------------------------------------
$secretsDir = Join-Path (Join-Path $PSScriptRoot "..") ".secrets"
$secretsDir = Resolve-Path (New-Item -ItemType Directory -Force -Path $secretsDir).FullName
Write-Ok ".secrets\ directory ready"

# -- Pull signing key PEM ------------------------------------------------------
Write-Host ""
Write-Host "Pulling signing key from Key Vault..."

$signingKeyPath = Join-Path $secretsDir "signing_key.pem"

# az keyvault secret show returns the PEM with literal \n escape sequences on Windows.
# We convert them back to real newlines here.
$signingKeyRaw = az keyvault secret show `
    --vault-name $KV_NAME `
    --name "diiac-signing-private-key-pem" `
    --query "value" -o tsv

if (-not $signingKeyRaw) {
    Write-Fail "Failed to retrieve diiac-signing-private-key-pem from Key Vault."
}

# Key Vault flattens PEM newlines to spaces on retrieval and may also return
# literal \n escape sequences on Windows.  Reconstruct proper 3-line PEM:
#   -----BEGIN PRIVATE KEY-----
#   <base64>
#   -----END PRIVATE KEY-----
$signingKeyPem = $signingKeyRaw -replace '\\n', "`n"                                                 # literal \n → real newline
$signingKeyPem = $signingKeyPem -replace '-----BEGIN PRIVATE KEY-----\s+', "-----BEGIN PRIVATE KEY-----`n"  # strip space/newline after header
$signingKeyPem = $signingKeyPem -replace '\s+-----END PRIVATE KEY-----',   "`n-----END PRIVATE KEY-----"    # strip space/newline before footer
$signingKeyPem = $signingKeyPem.Trim() + "`n"                                                        # trailing newline

# Validate PEM header
if (-not ($signingKeyPem -match "BEGIN")) {
    Write-Fail "Signing key PEM appears malformed. Check Key Vault secret 'diiac-signing-private-key-pem'."
}

# Write with Unix line endings (LF only) - required for openssl/cryptography library
$signingKeyBytes = [System.Text.Encoding]::UTF8.GetBytes(($signingKeyPem -replace "`r`n", "`n"))
[System.IO.File]::WriteAllBytes($signingKeyPath, $signingKeyBytes)

Write-Ok "Signing key -> .secrets\signing_key.pem"

# -- Pull non-PEM secrets ------------------------------------------------------
Write-Host ""
Write-Host "Pulling secrets..."

$adminToken = az keyvault secret show `
    --vault-name $KV_NAME --name "diiac-admin-api-token" --query "value" -o tsv
Write-Ok "ADMIN_API_TOKEN retrieved ($($adminToken.Length) chars)"

$openaiKey = az keyvault secret show `
    --vault-name $KV_NAME --name "diiac-openai-api-key" --query "value" -o tsv
Write-Ok "OPENAI_API_KEY retrieved"

$githubToken = ""
try {
    $githubToken = az keyvault secret show `
        --vault-name $KV_NAME --name "diiac-github-token" --query "value" -o tsv 2>$null
    if ($githubToken) {
        Write-Ok "GITHUB_TOKEN retrieved"
    } else {
        Write-Warn "diiac-github-token not found in Key Vault - Copilot LLM provider will be unavailable"
    }
} catch {
    Write-Warn "diiac-github-token not found in Key Vault - Copilot LLM provider will be unavailable"
}

# -- Build .env ----------------------------------------------------------------
Write-Host ""
Write-Host "Writing .env..."

$groupMap = "{`"${ENTRA_ADMIN_GROUP_ID}`":{`"role`":`"admin`"},`"${ENTRA_USER_GROUP_ID}`":{`"role`":`"standard`"}}"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$envContent = @"
# DIIaC v1.2.0 - $Customer local staging
# Generated by scripts/pull-keyvault-secrets.ps1 -Customer $Customer on $timestamp
# DO NOT COMMIT - this file contains secrets

# Ports
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173

# Runtime secrets
ADMIN_API_TOKEN=$adminToken

# LLM
LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=$openaiKey
OPENAI_MODEL=gpt-4o-mini
GITHUB_TOKEN=$githubToken
COPILOT_MODEL=gpt-4o

# Entra ID
AUTH_MODE=entra_jwt_rs256
ENTRA_ROLE_CLAIM=roles
ENTRA_EXPECTED_TENANT_ID=$ENTRA_TENANT_ID
ENTRA_EXPECTED_AUDIENCE=api://$ENTRA_API_APP_ID
ENTRA_EXPECTED_ISSUERS=https://login.microsoftonline.com/$ENTRA_TENANT_ID/v2.0,https://sts.windows.net/$ENTRA_TENANT_ID/
ENTRA_GROUP_TO_ROLE_JSON=$groupMap
ENTRA_PRINCIPAL_TO_ROLE_JSON={}
ENTRA_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/$ENTRA_TENANT_ID/v2.0/.well-known/openid-configuration
ENTRA_JWKS_URI=https://login.microsoftonline.com/$ENTRA_TENANT_ID/discovery/v2.0/keys

# Frontend MSAL
VITE_ENTRA_CLIENT_ID=$ENTRA_UI_APP_ID
VITE_ENTRA_TENANT_ID=$ENTRA_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_ENTRA_GROUP_MAP=$groupMap
"@

# Write .env with Unix line endings
$envBytes = [System.Text.Encoding]::UTF8.GetBytes(($envContent -replace "`r`n", "`n"))
[System.IO.File]::WriteAllBytes((Join-Path (Join-Path $PSScriptRoot "..") ".env"), $envBytes)

Write-Ok ".env written"

# -- Warn on missing IDs -------------------------------------------------------
Write-Host ""
if (-not $ENTRA_API_APP_ID) {
    Write-Warn "ENTRA_API_APP_ID is not set. Edit the script or set `$env:ENTRA_API_APP_ID before running."
}
if (-not $ENTRA_ADMIN_GROUP_ID) {
    Write-Warn "ENTRA_ADMIN_GROUP_ID not set - update ENTRA_GROUP_TO_ROLE_JSON in .env manually."
}

# -- Done ----------------------------------------------------------------------
Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "Secrets pulled successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next step:"
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build"
Write-Host ""
