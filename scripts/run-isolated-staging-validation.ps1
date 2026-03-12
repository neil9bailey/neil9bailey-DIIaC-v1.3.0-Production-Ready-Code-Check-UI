#!/usr/bin/env pwsh
param(
    [string]$ProjectName = "diiac_v121_codex",
    [int]$RuntimePort = 8100,
    [int]$BridgePort = 3101,
    [int]$FrontendPort = 5174,
    [switch]$PullBaseImages,
    [switch]$NoBuild,
    [switch]$SkipStartup
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { Fail $Message }
}

function Get-EnvValue([string]$Path, [string]$Key) {
    $line = Select-String -Path $Path -Pattern "^$Key=" | Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Line.Split("=", 2)[1]
}

function Invoke-Json([string]$Method, [string]$Uri, [hashtable]$Headers = $null, $Body = $null) {
    if ($Body -ne $null) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
    }
    return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $Headers
}

function Wait-ContainerHealthy([string]$Name, [int]$TimeoutSeconds = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = docker ps --filter "name=^$Name$" --format "{{.Status}}"
        if ($LASTEXITCODE -eq 0 -and $status) {
            if ($status -match "healthy" -or $status -match "^Up") {
                return
            }
        }
        Start-Sleep -Seconds 2
    }
    Fail "Timed out waiting for container '$Name' to become healthy/up."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

Write-Step "Preflight checks"
docker version | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Docker is not available." }

if (-not (Test-Path ".env")) {
    Fail ".env is missing. Run scripts/pull-keyvault-secrets.ps1 first."
}

$adminToken = Get-EnvValue ".env" "ADMIN_API_TOKEN"
if (-not $adminToken) {
    Fail "ADMIN_API_TOKEN not found in .env."
}

if (-not (Test-Path ".secrets/signing_key.pem")) {
    Fail ".secrets/signing_key.pem is missing."
}

if ($PullBaseImages) {
    Write-Step "Pulling base images"
    docker pull python:3.11-slim | Out-Host
    docker pull node:20-bullseye | Out-Host
    docker pull node:24-bookworm | Out-Host
}

$env:RUNTIME_HOST_PORT = "$RuntimePort"
$env:BRIDGE_HOST_PORT = "$BridgePort"
$env:FRONTEND_HOST_PORT = "$FrontendPort"

if (-not $SkipStartup) {
    Write-Step "Starting isolated staging stack"
    $composeArgs = @("-p", $ProjectName, "-f", "docker-compose.yml", "-f", "docker-compose.staging.yml", "up", "-d")
    if (-not $NoBuild) { $composeArgs += "--build" }
    docker compose @composeArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "docker compose up failed." }
}

Write-Step "Waiting for containers"
$runtimeContainer = "$ProjectName-governance-runtime-1"
$bridgeContainer = "$ProjectName-backend-ui-bridge-1"
$frontendContainer = "$ProjectName-frontend-1"
Wait-ContainerHealthy -Name $runtimeContainer
Wait-ContainerHealthy -Name $bridgeContainer
Wait-ContainerHealthy -Name $frontendContainer

Write-Step "Service checks"
$runtimeHealth = Invoke-Json -Method "GET" -Uri "http://localhost:$RuntimePort/health"
Assert-True ($runtimeHealth.status -eq "OK") "Runtime /health status is not OK."
Assert-True ($runtimeHealth.readiness.overall_ready -eq $true) "Runtime readiness is not true."

$authHeaders = @{ Authorization = "Bearer $adminToken" }
$adminHealth = Invoke-Json -Method "GET" -Uri "http://localhost:$RuntimePort/admin/health" -Headers $authHeaders
Assert-True ($adminHealth.status -eq "OK") "Admin health is not OK."
Assert-True ($adminHealth.key_mode -eq "configured") "Signing key mode is not configured."

$unauthCode = 0
try {
    Invoke-WebRequest -Method GET -Uri "http://localhost:$RuntimePort/admin/health" -ErrorAction Stop | Out-Null
    $unauthCode = 200
} catch {
    if ($_.Exception.Response) {
        $unauthCode = [int]$_.Exception.Response.StatusCode
    } else {
        throw
    }
}
Assert-True ($unauthCode -eq 401) "Admin health without token should return 401."

$bridgeAuthStatus = Invoke-Json -Method "GET" -Uri "http://localhost:$BridgePort/auth/status"
Assert-True ($bridgeAuthStatus.entra_enabled -eq $true) "Bridge Entra auth is not enabled."

$frontendReady = $false
$frontendLastError = ""
$frontendDeadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $frontendDeadline) {
    try {
        $frontendResponse = Invoke-WebRequest -Method GET -Uri "http://localhost:$FrontendPort/" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($frontendResponse.StatusCode -eq 200) {
            $frontendReady = $true
            break
        }
    } catch {
        $frontendLastError = $_.Exception.Message
        Start-Sleep -Seconds 2
    }
}
Assert-True $frontendReady "Frontend did not return HTTP 200 within timeout. Last error: $frontendLastError"

Write-Step "Governance flow checks"
$contextId = "codex-staging-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"

$roleInputPayload = @{
    execution_context_id = $contextId
    role = "CTO"
    domain = "Cloud Infrastructure Procurement"
    assertions = @("Multi-cloud strategy with Azure primary and >=15% cycle-time reduction within <=6 months")
    non_negotiables = @("Budget cap GBP 1.8M/year", "Microsoft Entra ID integration", "ISO 27001", "99.9% SLA")
    risk_flags = @("Single-vendor lock-in", "Shadow IT")
    evidence_refs = @("https://www.fortinet.com/products/secure-sd-wan", "urn:independent:analyst-report:2026q1")
}
$roleInputResult = Invoke-Json -Method "POST" -Uri "http://localhost:$RuntimePort/api/human-input/role" -Body $roleInputPayload
Assert-True ($roleInputResult.stored -eq $true) "Role input was not stored."

$compilePayload = @{
    execution_context_id = $contextId
    schema_id = "GENERAL_SOLUTION_BOARD_REPORT_V1"
    profile_id = "transport_profile_v1"
    reasoning_level = "R4"
    policy_level = "P4"
}
$compileResult = Invoke-Json -Method "POST" -Uri "http://localhost:$RuntimePort/api/governed-compile" -Body $compilePayload
$executionId = $compileResult.execution_id
Assert-True ([string]::IsNullOrWhiteSpace($executionId) -eq $false) "Governed compile did not return execution_id."

$verifyExecution = Invoke-Json -Method "GET" -Uri "http://localhost:$RuntimePort/verify/execution/$executionId"
Assert-True ($verifyExecution.status -eq "VERIFIABLE") "Execution verification is not VERIFIABLE."
Assert-True ($verifyExecution.ledger_match -eq $true) "Execution ledger match is false."

$verifyPackPayload = @{
    execution_id = $executionId
    pack_hash = $verifyExecution.pack_hash
    manifest_hash = $verifyExecution.manifest_hash
}
$verifyPack = Invoke-Json -Method "POST" -Uri "http://localhost:$RuntimePort/verify/pack" -Body $verifyPackPayload
Assert-True ($verifyPack.overall_valid -eq $true) "Pack verification overall_valid is false."

$signedExport = Invoke-Json -Method "GET" -Uri "http://localhost:$RuntimePort/decision-pack/$executionId/export-signed"
Assert-True ($signedExport.sigmeta.signature_alg -eq "Ed25519") "Signed export algorithm is not Ed25519."

$trustStatus = Invoke-Json -Method "GET" -Uri "http://localhost:$RuntimePort/trust/status"
Assert-True ($trustStatus.ledger_records -ge 1) "Trust ledger has no records."

$auditPayload = @{ execution_ids = @($executionId) }
$auditResult = Invoke-Json -Method "POST" -Uri "http://localhost:$RuntimePort/admin/audit-export" -Headers $authHeaders -Body $auditPayload
Assert-True ([string]::IsNullOrWhiteSpace($auditResult.audit_export_id) -eq $false) "Audit export did not return an id."

Write-Step "Validation summary"
[pscustomobject]@{
    project_name = $ProjectName
    runtime_url = "http://localhost:$RuntimePort"
    bridge_url = "http://localhost:$BridgePort"
    frontend_url = "http://localhost:$FrontendPort"
    execution_id = $executionId
    audit_export_id = $auditResult.audit_export_id
    status = "PASS"
} | ConvertTo-Json -Depth 5 | Write-Host

Write-Host ""
Write-Host "All isolated staging checks passed." -ForegroundColor Green
