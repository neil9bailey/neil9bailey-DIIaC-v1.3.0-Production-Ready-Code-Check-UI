# DIIaC v1.2.0 -- Local staging launcher (Windows PowerShell 5.1+)
#
# Pulls secrets from Azure Key Vault, then starts the full Docker stack.
# Run this instead of the two-step manual process.
#
# Usage:
#   .\start-staging.ps1                # pull secrets + build + start (foreground)
#   .\start-staging.ps1 -Detach        # pull secrets + build + start (background)
#   .\start-staging.ps1 -NoBuild       # pull secrets + start without rebuild
#   .\start-staging.ps1 -SecretsOnly   # pull secrets only, skip stack start
#
# Prerequisites: Docker Desktop running, Azure CLI installed, az login done.

param(
    [switch]$Detach,
    [switch]$NoBuild,
    [switch]$SecretsOnly
)

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Header { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Ok     { param($msg) Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }
function Write-Step   { param($n, $msg) Write-Host ""; Write-Host "-- Step $n : $msg" -ForegroundColor Cyan }

Write-Host ""
Write-Header "DIIaC v1.2.0 -- Local Staging Launcher"
Write-Header "========================================"
Write-Host ""

# ── Step 1: Check Docker Desktop ──────────────────────────────────────────────
Write-Step 1 "Checking Docker Desktop"

try { $null = Get-Command docker -ErrorAction Stop } catch {
    Write-Fail "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
}

$null = docker info 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop is not running. Start it from the system tray and try again."
}
Write-Ok "Docker Desktop is running"

# ── Step 2: Pull secrets ──────────────────────────────────────────────────────
Write-Step 2 "Pulling secrets from Azure Key Vault"

$pullScript = [string](Join-Path $PSScriptRoot "scripts\pull-keyvault-secrets.ps1")
if (-not (Test-Path $pullScript)) {
    Write-Fail "Pull script not found at: $pullScript"
}

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& $pullScript
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Secret pull failed. See errors above."
}

if ($SecretsOnly) {
    Write-Host ""
    Write-Warn "SecretsOnly flag set -- skipping stack start."
    exit 0
}

# ── Step 3: Verify outputs before starting ────────────────────────────────────
Write-Step 3 "Verifying outputs"

$envPath  = [string](Join-Path $PSScriptRoot ".env")
$pemPath  = [string](Join-Path $PSScriptRoot ".secrets\signing_key.pem")

if (-not (Test-Path $envPath))  { Write-Fail ".env was not created by the pull script." }
if (-not (Test-Path $pemPath))  { Write-Fail ".secrets\signing_key.pem was not created by the pull script." }

$pemContent = [string](Get-Content $pemPath -Raw)
if (-not ($pemContent -match "BEGIN")) {
    Write-Fail ".secrets\signing_key.pem does not look like a valid PEM file."
}
Write-Ok ".env present"
Write-Ok ".secrets\signing_key.pem valid"

# ── Step 4: Start the stack ───────────────────────────────────────────────────
Write-Step 4 "Starting DIIaC stack"

$composeArgs = @("-f", "docker-compose.yml", "-f", "docker-compose.staging.yml", "up")
if (-not $NoBuild) { $composeArgs += "--build" }
if ($Detach)       { $composeArgs += "-d" }

Write-Host ""
if ($NoBuild) { Write-Warn "NoBuild flag set -- skipping image rebuild." }
if ($Detach)  { Write-Warn "Detach flag set -- starting in background." }
Write-Host ""

docker compose @composeArgs

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Compose failed. See errors above."
}

# ── Done (detached mode only -- foreground stays in compose output) ───────────
if ($Detach) {
    Write-Host ""
    Write-Header "========================================"
    Write-Header "Stack started."
    Write-Host ""
    Write-Host "  Frontend : http://localhost:5173"
    Write-Host "  Runtime  : http://localhost:8000/health"
    Write-Host "  Bridge   : http://localhost:3001"
    Write-Host ""
    Write-Host "  Follow logs : docker compose logs -f"
    Write-Host "  Stop        : docker compose -f docker-compose.yml -f docker-compose.staging.yml down"
    Write-Host ""
}
