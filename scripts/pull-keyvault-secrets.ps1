# DIIaC v1.2.0 -- Pull secrets from Azure Key Vault for local Docker Desktop staging
# Windows PowerShell 5.1+ compatible
#
# Usage (from repository root):
#   .\scripts\pull-keyvault-secrets.ps1
#
# Prerequisites:
#   - Azure CLI installed (https://learn.microsoft.com/cli/azure/install-azure-cli-windows)
#   - az login completed
#   - Key Vault populated (see VENDORLOGIC_LOCAL_STAGING_GUIDE.md)
#
# Outputs:
#   .env                      -- all non-PEM secrets for docker compose
#   .secrets\signing_key.pem  -- Ed25519 signing key (bind-mounted by compose)

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration -- Vendorlogic instance ──────────────────────────────────────
# Loaded from customer-config/vendorlogic/config.env (public IDs, safe to commit).
# Override any value by setting $env:VARIABLE before running this script.

# $repoRoot is the repo root (parent of the scripts\ folder) -- always a plain string
$repoRoot   = [string](Split-Path -Parent $PSScriptRoot)
$configFile = [string](Join-Path (Join-Path $repoRoot "customer-config") "vendorlogic\config.env")
$configVars = @{}

if (Test-Path $configFile) {
    Get-Content $configFile | Where-Object { $_ -match '^\s*[^#]\S+=\S*' } | ForEach-Object {
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) { $configVars[$parts[0].Trim()] = $parts[1].Trim() }
    }
}

function Cfg { param($key, $default) if ($configVars.ContainsKey($key)) { $configVars[$key] } else { $default } }

# PS 5.1-compatible null-coalescing (no ?? operator)
function Nvl { param($envVal, $cfgVal) if ($null -ne $envVal -and $envVal -ne '') { $envVal } else { $cfgVal } }

$KV_NAME              = [string](Nvl $env:KEY_VAULT_NAME          (Cfg "KEY_VAULT_NAME"          "kv-diiac-vendorlogic"))
$ENTRA_TENANT_ID      = [string](Nvl $env:AZURE_TENANT_ID         (Cfg "AZURE_TENANT_ID"         "1384b1c5-2bae-45a1-a4b4-e94e3315eb41"))
$ENTRA_API_APP_ID     = [string](Nvl $env:ENTRA_API_APP_ID        (Cfg "ENTRA_API_APP_ID"        "b726558d-f1c6-48f7-8a3d-72d5db818d0f"))
$ENTRA_UI_APP_ID      = [string](Nvl $env:ENTRA_UI_APP_ID         (Cfg "ENTRA_UI_APP_ID"         "b726558d-f1c6-48f7-8a3d-72d5db818d0f"))
$ENTRA_ADMIN_GROUP_ID = [string](Nvl $env:ENTRA_ADMIN_GROUP_ID    (Cfg "ENTRA_ADMIN_GROUP_ID"    "81786818-de16-4115-b061-92fce74b00bd"))
$ENTRA_USER_GROUP_ID  = [string](Nvl $env:ENTRA_STANDARD_GROUP_ID (Cfg "ENTRA_STANDARD_GROUP_ID" "9c7dd0d4-5b44-4811-b167-e52df21092d8"))

# ASCII status prefixes -- avoids UTF-8/Windows-1252 encoding issues in PS 5.1
function Write-Ok   { param($msg) Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "DIIaC v1.2.0 -- Key Vault secret pull (Windows)" -ForegroundColor Cyan
Write-Host "------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

# ── Check az CLI ──────────────────────────────────────────────────────────────
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Fail "Azure CLI not found. Download from https://aka.ms/installazurecliwindows"
}

# ── Check login ───────────────────────────────────────────────────────────────
$account = [string](az account show --query "user.name" -o tsv 2>$null)
if (-not $account) {
    Write-Warn "Not logged in to Azure CLI. Running az login..."
    az login
    $account = [string](az account show --query "user.name" -o tsv)
}
Write-Ok "Logged in as: $account"

# Auto-detect tenant if not set
if (-not $ENTRA_TENANT_ID) {
    $ENTRA_TENANT_ID = [string](az account show --query tenantId -o tsv)
    Write-Warn "ENTRA_TENANT_ID not set -- using active tenant: $ENTRA_TENANT_ID"
}

# ── Check Key Vault ───────────────────────────────────────────────────────────
$kvCheck = az keyvault show --name $KV_NAME --query name -o tsv 2>$null
if (-not $kvCheck) {
    Write-Fail "Key Vault '$KV_NAME' not found. Check KV_NAME or provision it first."
}
Write-Ok "Key Vault found: $KV_NAME"

# ── Create .secrets directory ─────────────────────────────────────────────────
# Use .FullName (plain string) instead of Resolve-Path (returns PathInfo object)
$secretsDirPath = [string](Join-Path $repoRoot ".secrets")
$secretsDir     = [string](New-Item -ItemType Directory -Force -Path $secretsDirPath).FullName
Write-Ok ".secrets\ directory ready"

# ── Pull signing key PEM ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "Pulling signing key from Key Vault..."

# $signingKeyPath is a plain string -- safe to pass to .NET File APIs
$signingKeyPath = [string](Join-Path $secretsDir "signing_key.pem")

# az keyvault secret show returns the PEM with literal \n escape sequences on Windows.
# We convert them back to real newlines here.
$signingKeyRaw = [string](az keyvault secret show `
    --vault-name $KV_NAME `
    --name "diiac-signing-private-key-pem" `
    --query "value" -o tsv)

if (-not $signingKeyRaw) {
    Write-Fail "Failed to retrieve diiac-signing-private-key-pem from Key Vault."
}

# Normalise line endings -- Key Vault may return \n as literal or real
$signingKeyPem = $signingKeyRaw -replace '\\n', "`n"

# Validate PEM header
if (-not ($signingKeyPem -match "BEGIN")) {
    Write-Fail "Signing key PEM appears malformed. Check Key Vault secret 'diiac-signing-private-key-pem'."
}

# Remove any existing file first -- handles read-only flag and most ACL restrictions
if (Test-Path $signingKeyPath) {
    Remove-Item -Force -Path $signingKeyPath
}

# Write with Unix line endings (LF only) -- required for openssl/cryptography library
$signingKeyBytes = [System.Text.Encoding]::UTF8.GetBytes(($signingKeyPem -replace "`r`n", "`n"))
[System.IO.File]::WriteAllBytes($signingKeyPath, $signingKeyBytes)

Write-Ok "Signing key -> .secrets\signing_key.pem"

# ── Pull non-PEM secrets ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "Pulling secrets..."

$adminToken = [string](az keyvault secret show `
    --vault-name $KV_NAME --name "diiac-admin-api-token" --query "value" -o tsv)
Write-Ok "ADMIN_API_TOKEN retrieved ($($adminToken.Length) chars)"

$openaiKey = [string](az keyvault secret show `
    --vault-name $KV_NAME --name "diiac-openai-api-key" --query "value" -o tsv)
Write-Ok "OPENAI_API_KEY retrieved"

# ── Build .env ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Writing .env..."

$groupMap  = "{`"${ENTRA_ADMIN_GROUP_ID}`":{`"role`":`"admin`"},`"${ENTRA_USER_GROUP_ID}`":{`"role`":`"standard`"}}"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$envPath   = [string](Join-Path $repoRoot ".env")

$envContent = @"
# DIIaC v1.2.0 -- Vendorlogic local staging
# Generated by scripts/pull-keyvault-secrets.ps1 on $timestamp
# DO NOT COMMIT -- this file contains secrets

# Ports
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173

# Runtime secrets
ADMIN_API_TOKEN=$adminToken

# LLM
OPENAI_API_KEY=$openaiKey
OPENAI_MODEL=gpt-4o-mini

# Entra ID
AUTH_MODE=entra_jwt_rs256
ENTRA_ROLE_CLAIM=groups
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
[System.IO.File]::WriteAllBytes($envPath, $envBytes)

Write-Ok ".env written"

# ── Warn on missing IDs ───────────────────────────────────────────────────────
Write-Host ""
if (-not $ENTRA_API_APP_ID) {
    Write-Warn "ENTRA_API_APP_ID is not set. Edit the script or set `$env:ENTRA_API_APP_ID before running."
}
if (-not $ENTRA_ADMIN_GROUP_ID) {
    Write-Warn "ENTRA_ADMIN_GROUP_ID not set -- update ENTRA_GROUP_TO_ROLE_JSON in .env manually."
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "------------------------------------------------" -ForegroundColor Green
Write-Host "Secrets pulled successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next step:"
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build"
Write-Host ""
