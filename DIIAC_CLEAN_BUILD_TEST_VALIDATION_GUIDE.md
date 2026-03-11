# DIIaC v1.2.0 — Complete Clean Build, Test & Validation Guide

## Context

Full clean-down of your local repo, rebuild from scratch, and validate every
integration point: Azure Key Vault secrets, Entra ID authentication, ChatGPT
LLM, Copilot LLM, the customer onboarding flow, and the full governance
pipeline. Designed for **Windows PowerShell** with **Docker Desktop**.

**Branch:** `claude/diiac-production-code-check-LqTNo`

---

## PHASE 0 — FULL CLEAN-DOWN (Nuclear Reset)

Open PowerShell as Administrator. Run from your repo root:

```powershell
# 0.1 — Stop and remove ALL DIIaC containers, networks, volumes
docker compose -f docker-compose.yml -f docker-compose.staging.yml down -v --remove-orphans

# 0.2 — Prune Docker build cache (forces clean rebuild)
docker builder prune -af

# 0.3 — Remove dangling images and unused volumes
docker system prune -af --volumes

# 0.4 — Delete generated secrets and env files (we'll regenerate from Key Vault)
Remove-Item -Force -ErrorAction SilentlyContinue .env
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .secrets

# 0.5 — Clear runtime output directories (keep dirs for Docker volume mounts)
Get-ChildItem artifacts -Exclude .gitkeep -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem exports -Exclude .gitkeep -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem audit_exports -Exclude .gitkeep -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem human_input -Exclude .gitkeep -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# 0.6 — Remove node_modules (fresh install)
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue Frontend\node_modules
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue backend-ui-bridge\node_modules

# 0.7 — Remove Python cache
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue __pycache__
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .pytest_cache
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .venv
```

**Checkpoint 0:** Run `docker ps -a` — should show NO diiac containers. Run `ls .env` — should say file not found.

---

## PHASE 1 — AZURE KEY VAULT: Pull Secrets

### 1.1 — Azure CLI Login

```powershell
az login
az account show
# Confirm you see the Vendorlogic tenant: 1384b1c5-2bae-45a1-a4b4-e94e3315eb41
```

If wrong tenant:
```powershell
az login --tenant 1384b1c5-2bae-45a1-a4b4-e94e3315eb41
```

### 1.2 — Verify Key Vault Access

```powershell
az keyvault show --name kv-diiac-vendorlogic --query name -o tsv
# Expected: kv-diiac-vendorlogic
```

If this fails:
- Check subscription: `az account list -o table`
- Check RBAC: you need "Key Vault Secrets User" role on the vault
- Grant yourself: `az role assignment create --role "Key Vault Secrets Officer" --assignee (az ad signed-in-user show --query id -o tsv) --scope (az keyvault show --name kv-diiac-vendorlogic --query id -o tsv)`

### 1.3 — Verify All 5 Secrets Exist in Key Vault

```powershell
az keyvault secret list --vault-name kv-diiac-vendorlogic -o table
```

You must see these 5 secrets (minimum 3 required):

| Secret Name | Required | Purpose |
|-------------|----------|---------|
| `diiac-admin-api-token` | YES | Bearer token for `/admin/*` endpoints |
| `diiac-signing-private-key-pem` | YES | Ed25519 signing key for decision packs |
| `diiac-openai-api-key` | YES | OpenAI API key (`sk-...`) for ChatGPT provider |
| `diiac-github-token` | Recommended | GitHub PAT for Copilot LLM provider (via Azure AI inference) |
| `diiac-entra-client-secret` | Optional | Entra app client secret |

**If any required secret is missing**, create it now:

```powershell
# Admin token (generate random)
$token = openssl rand -hex 32
az keyvault secret set --vault-name kv-diiac-vendorlogic --name "diiac-admin-api-token" --value $token

# Signing key (generate Ed25519)
openssl genpkey -algorithm ed25519 -out diiac_signing_key.pem
az keyvault secret set --vault-name kv-diiac-vendorlogic --name "diiac-signing-private-key-pem" --file diiac_signing_key.pem
Remove-Item diiac_signing_key.pem

# OpenAI key (from https://platform.openai.com/api-keys)
az keyvault secret set --vault-name kv-diiac-vendorlogic --name "diiac-openai-api-key" --value "sk-YOUR-KEY-HERE"

# GitHub token for Copilot (from https://github.com/settings/tokens — needs "copilot" scope)
az keyvault secret set --vault-name kv-diiac-vendorlogic --name "diiac-github-token" --value "ghp-YOUR-TOKEN-HERE"
```

### 1.4 — Run the Pull Script

The pull script reads public IDs from `customer-config/vendorlogic/config.env`
and secrets from Key Vault, then writes `.env` and `.secrets/signing_key.pem`.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\pull-keyvault-secrets.ps1
```

**Expected output:**
```
DIIaC v1.2.0 — Key Vault secret pull (Windows)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Logged in as: you@vendorlogic.com
✓ Key Vault found: kv-diiac-vendorlogic
✓ Signing key → .secrets\signing_key.pem
✓ ADMIN_API_TOKEN retrieved (64 chars)
✓ OPENAI_API_KEY retrieved
✓ GITHUB_TOKEN retrieved
✓ .env written
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Secrets pulled successfully.
```

> **Note:** If `diiac-github-token` is not in Key Vault, you'll see a warning:
> `"diiac-github-token not found in Key Vault — Copilot LLM provider will be unavailable"`.
> This is non-fatal — ChatGPT will still work; only the Copilot provider will be disabled.

### 1.5 — Validate the Generated Files

```powershell
# Check .env has real values (not placeholders)
Select-String "ADMIN_API_TOKEN" .env
# Should show a 64-char hex string, NOT empty

Select-String "OPENAI_API_KEY" .env
# Should show sk-...

Select-String "GITHUB_TOKEN" .env
# Should show ghp-... (or empty if not in Key Vault)

# Check signing key PEM
Get-Content .secrets\signing_key.pem -First 1
# Must show: -----BEGIN PRIVATE KEY-----

# Check .env has Entra config
Select-String "AUTH_MODE" .env
# Should show: AUTH_MODE=entra_jwt_rs256

Select-String "VITE_ENTRA_CLIENT_ID" .env
# Should show: VITE_ENTRA_CLIENT_ID=b726558d-f1c6-48f7-8a3d-72d5db818d0f

# Check LLM models
Select-String "OPENAI_MODEL" .env
# Should show: OPENAI_MODEL=gpt-4o-mini

Select-String "COPILOT_MODEL" .env
# Should show: COPILOT_MODEL=gpt-4o
```

**Checkpoint 1:** `.env` and `.secrets\signing_key.pem` both exist with real values. Key Vault integration CONFIRMED.

---

## PHASE 2 — ENTRA ID: Verify App Registrations

### 2.1 — Verify API App Registration Exists

```powershell
az ad app show --id b726558d-f1c6-48f7-8a3d-72d5db818d0f --query "{name:displayName, appId:appId}" -o table
# Expected: DIIaC-API-Vendorlogic
```

If not found, follow `ENTRA_ID_SETUP_GUIDE.md` Step 5a to create it.

### 2.2 — Verify Redirect URIs Include localhost

> **Important:** MSAL v5 uses Authorization Code + PKCE, which requires the **SPA**
> platform — not Web. URIs under the Web platform cause `400 Bad Request` on token exchange.

```powershell
az ad app show --id b726558d-f1c6-48f7-8a3d-72d5db818d0f --query "spa.redirectUris" -o tsv
```

Must include: `http://localhost:5173/auth/callback`

If missing:
```powershell
az ad app update --id b726558d-f1c6-48f7-8a3d-72d5db818d0f --spa-redirect-uris "http://localhost:5173/auth/callback" "http://localhost:5173"
```

### 2.3 — Verify Security Groups Exist

```powershell
az ad group show --group "DIIaC-Admins" --query "{name:displayName, id:id}" -o table
az ad group show --group "DIIaC-Users" --query "{name:displayName, id:id}" -o table
```

Expected group IDs:
- DIIaC-Admins: `81786818-de16-4115-b061-92fce74b00bd`
- DIIaC-Users: `9c7dd0d4-5b44-4811-b167-e52df21092d8`

### 2.4 — Verify You Are in the Admin Group

```powershell
az ad group member check --group "DIIaC-Admins" --member-id (az ad signed-in-user show --query id -o tsv) --query value -o tsv
# Expected: true
```

If false:
```powershell
az ad group member add --group "DIIaC-Admins" --member-id (az ad signed-in-user show --query id -o tsv)
```

### 2.5 — Verify Group Claims are Configured on the API App

Go to **Azure Portal > Entra ID > App registrations > DIIaC-API-Vendorlogic > Token configuration**
- Must have "groups" claim configured with "Security groups" + "Group ID" selected
- If not configured, add it (see `ENTRA_ID_SETUP_GUIDE.md` Step 5d)

**Checkpoint 2:** Entra app registration, redirect URIs, groups, and group claims all verified.

---

## PHASE 3 — BUILD: Docker Compose Full Stack

### 3.1 — Ensure Docker Desktop Is Running

```powershell
docker version
# Must show both Client AND Server version
```

### 3.2 — Pull Fresh Base Images

```powershell
docker pull python:3.11-slim
docker pull node:20-bullseye
docker pull node:24-bookworm
```

### 3.3 — Build and Start the Full Staging Stack

```powershell
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

**Keep this terminal open. Watch the logs.**

What happens in order:
1. `governance-runtime` starts (Python 3.11 slim, installs Flask + cryptography from `requirements.txt`, reads signing key from `/run/secrets/signing_key`, starts `app.py` on port 8000)
2. `backend-ui-bridge` builds (Node 20 Bullseye + PowerShell, `npm ci`, starts `server.js` on port 3001)
3. `frontend` builds (Node 24 Bookworm, `npm ci`, Vite dev server on port 5173)

**Expected healthy output (wait for ALL three):**
```
governance-runtime  | * Running on all addresses (0.0.0.0)
governance-runtime  | * Running on http://127.0.0.1:8000
backend-ui-bridge   | DIIaC Bridge listening on port 3001
frontend            | VITE v7.x.x  ready in Xms
frontend            | ➜  Local:   http://localhost:5173/
```

### 3.4 — If Build Fails: Debug Steps

**Python runtime fails to start:**
```powershell
docker compose logs governance-runtime
# Common issues:
# - requirements.txt: package version mismatch -> check error, pin correct version
# - PEM format: signing key has CRLF line endings -> re-run pull-keyvault-secrets.ps1
# - Invalid PEM data -> you'll now see a clear error message:
#   "SIGNING_PRIVATE_KEY_PEM is set but contains invalid key data: ..."
#   with instructions to regenerate the key
# - Port 8000 in use -> set RUNTIME_HOST_PORT=8001 in .env
```

**Bridge fails to start:**
```powershell
docker compose logs backend-ui-bridge
# Common issues:
# - npm install failure -> check Node version (needs 20+)
# - PYTHON_BASE_URL wrong -> compose sets it to http://governance-runtime:8000 (correct)
# - Port 3001 in use -> set BRIDGE_HOST_PORT=3002 in .env
```

**Frontend fails to start:**
```powershell
docker compose logs frontend
# Common issues:
# - npm install failure -> check Node version (needs 24+)
# - TypeScript compile errors -> check error output
# - Port 5173 in use -> set FRONTEND_HOST_PORT=5174 in .env
```

**Checkpoint 3:** All 3 containers running. `docker compose ps` shows all services "Up".

---

## PHASE 4 — VALIDATE: Governance Runtime (Port 8000)

Open a NEW PowerShell window (keep Docker logs running in the first one).

### 4.1 — Health Check (No Auth Required)

```powershell
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json -Depth 5
```

**Expected:** `"status": "OK"`, `"overall_ready": true`

If `overall_ready: false` — check which sub-check failed in the response.

### 4.2 — Admin Health (Auth Required)

```powershell
$token = (Select-String "ADMIN_API_TOKEN=" .env).Line.Split("=",2)[1]
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod http://localhost:8000/admin/health -Headers $headers | ConvertTo-Json -Depth 5
```

**Expected:**
- `"status": "OK"`
- `"signing_enabled": true`
- `"key_mode": "configured"` (NOT "ephemeral")
- `"strict_deterministic_mode": true`

If `key_mode: "ephemeral"`:
```powershell
# Signing key didn't load from .secrets\signing_key.pem
# Check the bind mount:
docker compose exec governance-runtime cat /run/secrets/signing_key | Select-Object -First 1
# Must show: -----BEGIN PRIVATE KEY-----
```

### 4.3 — Admin Auth Denial (Security Test)

```powershell
try { Invoke-RestMethod http://localhost:8000/admin/health } catch { $_.Exception.Response.StatusCode }
# Expected: 401 (Unauthorized)
```

### 4.4 — Business Profiles

```powershell
(Invoke-RestMethod http://localhost:8000/api/business-profiles).Count
# Expected: 8 (sector profiles)
```

### 4.5 — Admin Metrics

```powershell
Invoke-RestMethod http://localhost:8000/admin/metrics -Headers $headers | ConvertTo-Json -Depth 5
# Expected: health_status: "OK", alerts: []
```

**Checkpoint 4:** Runtime healthy, signing configured, admin auth enforced, 8 business profiles loaded.

---

## PHASE 5 — VALIDATE: First Governed Compile (End-to-End Pipeline)

### 5.1 — Submit CTO Role Input

```powershell
$contextId = "vendorlogic-test-$(Get-Date -UFormat %s)"

$roleInput = @{
    execution_context_id = $contextId
    role = "CTO"
    domain = "Cloud Infrastructure Procurement"
    assertions = @("Multi-cloud strategy with Azure primary", "Zero-trust security", "UK data residency")
    non_negotiables = @("Microsoft Entra ID integration", "ISO 27001", "99.9% SLA")
    risk_flags = @("Single-vendor lock-in", "Shadow IT")
    evidence_refs = @("REF-001: Board tech mandate Q1 2026")
} | ConvertTo-Json

Invoke-RestMethod -Method POST http://localhost:8000/api/human-input/role -ContentType "application/json" -Body $roleInput | ConvertTo-Json -Depth 5
```

**Expected:** Status 201, role input accepted.

### 5.2 — Run Governed Compile

```powershell
$compileInput = @{
    execution_context_id = $contextId
    schema_id = "GENERAL_SOLUTION_BOARD_REPORT_V1"
    profile_id = "transport_profile_v1"
    reasoning_level = "R4"
    policy_level = "P4"
} | ConvertTo-Json

$result = Invoke-RestMethod -Method POST http://localhost:8000/api/governed-compile -ContentType "application/json" -Body $compileInput
$execId = $result.execution_id
Write-Host "Execution ID: $execId"
$result | ConvertTo-Json -Depth 10
```

**Expected:** Status 201, execution_id returned, deterministic governance output.

> **Note on schema_id and profile_id:** Use `GENERAL_SOLUTION_BOARD_REPORT_V1` and
> `transport_profile_v1` — these are the IDs used in the automated test suite. The
> runtime maps profile IDs to loaded sector profiles.

### 5.3 — Verify Execution (Trust Ledger)

```powershell
Invoke-RestMethod http://localhost:8000/verify/execution/$execId | ConvertTo-Json -Depth 5
# Expected: "status": "VERIFIABLE", "ledger_match": true
```

### 5.4 — Verify Merkle Tree

```powershell
Invoke-RestMethod http://localhost:8000/executions/$execId/merkle | ConvertTo-Json -Depth 5
# Expected: merkle_root hash, levels array
```

### 5.5 — Verify Signed Export (Ed25519)

```powershell
Invoke-RestMethod http://localhost:8000/decision-pack/$execId/export-signed | ConvertTo-Json -Depth 10
# Expected: signature_alg: "Ed25519", signing_key_id: non-empty
```

### 5.6 — Verify Trust Ledger Status

```powershell
Invoke-RestMethod http://localhost:8000/trust/status | ConvertTo-Json -Depth 5
# Expected: ledger_records >= 1
```

### 5.7 — Admin Audit Export

```powershell
$auditBody = @{ execution_ids = @($execId) } | ConvertTo-Json
$audit = Invoke-RestMethod -Method POST http://localhost:8000/admin/audit-export -ContentType "application/json" -Body $auditBody -Headers $headers
Write-Host "Audit Export ID: $($audit.audit_export_id)"
```

**Checkpoint 5:** Full governance pipeline working — input, compile, verify, sign, audit.

---

## PHASE 6 — VALIDATE: Backend-UI-Bridge (Port 3001)

### 6.1 — Bridge Health

```powershell
Invoke-RestMethod http://localhost:3001/health | ConvertTo-Json -Depth 5
# Expected: 200 OK with status information
```

### 6.2 — Auth Status (Public Endpoint)

```powershell
Invoke-RestMethod http://localhost:3001/auth/status | ConvertTo-Json -Depth 5
# Expected: auth_mode: "entra_jwt_rs256", entra_enabled: true, tenant_id and audience populated
```

### 6.3 — Bridge-to-Runtime Connectivity

```powershell
# The bridge proxies to the runtime. Test via bridge:
Invoke-RestMethod http://localhost:3001/api/business-profiles | ConvertTo-Json -Depth 5
# Expected: Same 8 profiles as direct runtime call
```

### 6.4 — Admin Integrations Health (via Bridge)

This requires a valid Entra JWT in staging mode. You can test this via the UI
after login (Phase 8), or temporarily check from the admin console panel.

The bridge health endpoint at `/admin/integrations/health` reports:
- Entra auth status (mode, tenant, audience, JWKS)
- LLM provider status (OpenAI configured, Copilot configured, models)
- Signing status
- Approval queue health

**Checkpoint 6:** Bridge healthy, connected to runtime, Entra auth mode active.

---

## PHASE 7 — VALIDATE: LLM Integration (ChatGPT & Copilot)

### 7.1 — Check LLM Configuration in Bridge

```powershell
docker compose exec backend-ui-bridge env | Select-String "LLM|OPENAI|GITHUB_TOKEN|COPILOT"
```

**Expected (staging mode):**
```
LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=false
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
GITHUB_TOKEN=ghp-...
COPILOT_MODEL=gpt-4o
```

### 7.2 — ChatGPT (OpenAI) Integration

The bridge uses the OpenAI Node.js SDK (`openai` package) to call GPT models.

**Provider file:** `backend-ui-bridge/llm-ingestion/providers/openai.js`
**Default model:** `gpt-4o-mini` (configurable via `OPENAI_MODEL` env var)
**Auth:** `OPENAI_API_KEY` environment variable

The ChatGPT provider is used when the frontend sends `provider: "ChatGPT"` in
governance decision or governed compile requests.

### 7.3 — Copilot (GitHub Models) Integration

The Copilot provider is a **real, production implementation** — NOT a stub. It
uses the OpenAI SDK pointed at the Azure AI models inference endpoint
(`https://models.inference.ai.azure.com`) with GitHub token authentication.

**Provider file:** `backend-ui-bridge/llm-ingestion/providers/copilot.js`
**Default model:** `gpt-4o` (configurable via `COPILOT_MODEL` env var)
**Auth:** `GITHUB_TOKEN` environment variable
**Endpoint:** `https://models.inference.ai.azure.com`

The Copilot provider is used when the frontend sends `provider: "Copilot"` in
governance decision or governed compile requests. If `GITHUB_TOKEN` is not set,
the provider is disabled and selecting Copilot in the UI will return an error.

**How provider selection flows through the system:**

```
Frontend (provider selector)
  → POST /govern/decision { provider: "Copilot" }
  → server.js generateAI() checks provider param
  → if "Copilot": uses copilotClient (OpenAI SDK → Azure AI inference)
  → if "ChatGPT": uses openai client (OpenAI SDK → OpenAI API)
```

### 7.4 — LLM Ingestion Endpoint

The LLM ingestion audit endpoint is mounted at `/api/ingest/llm`. It captures
LLM call metadata (prompt hash, response hash, model, provider) for governance
audit trails.

```powershell
# This endpoint requires LLM_INGESTION_ENABLED=true (set in staging mode)
# It's used programmatically by the bridge, not typically called directly
```

### 7.5 — Verify Both Providers Show in Admin Health

After logging in to the frontend (Phase 8), navigate to the Admin Console.
The integrations health panel should show:

```
LLM:
  openai:
    configured: true
    api_key: configured
    model: gpt-4o-mini
  copilot:
    configured: true (or false if GITHUB_TOKEN missing)
    api_key: configured (or missing)
    model: gpt-4o
```

**Checkpoint 7:** ChatGPT connected via OpenAI API (real calls). Copilot connected via GitHub Models API (real calls). Both providers are production implementations.

---

## PHASE 8 — VALIDATE: Frontend & Entra SSO (Port 5173)

### 8.1 — Open the UI

Open your browser: **http://localhost:5173**

### 8.2 — Entra ID Login Flow

1. You should see the DIIaC landing page with a **Sign In** button
2. Click **Sign In** — redirects to `login.microsoftonline.com`
3. Sign in with your Vendorlogic Entra ID credentials
4. You'll be redirected back to `http://localhost:5173/auth/callback`
5. The app should load with your role (admin/standard based on group membership)

**If login fails — debug checklist:**
- Open browser DevTools (F12) > Console tab > look for MSAL errors
- Check redirect URI is registered: `http://localhost:5173/auth/callback`
- Check `VITE_ENTRA_CLIENT_ID` in `.env` matches the Entra app registration
- Check browser isn't blocking popups/redirects

### 8.3 — Verify Role Mapping

Once logged in:
- **Admin users** (in DIIaC-Admins group) — see Admin Console panel
- **Standard users** (in DIIaC-Users group) — see governance workflow panels only
- **Unknown groups** — default to viewer role

Role mapping is driven by the `VITE_ENTRA_GROUP_MAP` env var, which maps
Entra group OIDs to DIIaC roles. The frontend resolves roles from JWT `groups`
claim using `Frontend/src/auth/roleMapping.ts`.

### 8.4 — Test UI Panels

| Panel | Test Action | Expected Result |
|-------|-------------|-----------------|
| Human Input | Submit an intent/directive | Returns 201, input stored |
| Governed CTO Strategy | Select provider (ChatGPT/Copilot), execute | Returns execution ID |
| Multi-Role Governed Compile | Full compile with provider selection | Returns compile output |
| Report Viewer | View/download a report | Shows report content |
| Trust Dashboard | Check ledger | Shows verification status |
| Admin Console (admin only) | Run health check | Shows system health |

### 8.5 — Test Provider Selection in UI

1. Navigate to the Governed CTO Strategy or Multi-Role Governed Compile panel
2. Select **ChatGPT** as provider — execute a governance decision
3. Verify the response includes LLM-synthesized content
4. Select **Copilot** as provider — execute a governance decision
5. Verify the response includes LLM-synthesized content (requires GITHUB_TOKEN)
6. If Copilot fails with "GITHUB_TOKEN is missing", verify Phase 7.1

**Checkpoint 8:** Frontend loads, Entra SSO works, role-based panels visible, both LLM providers selectable.

---

## PHASE 9 — VALIDATE: Run Automated Test Suites

> **Important:** The E2E smoke test and production readiness check scripts
> start their own `app.py` subprocess on port 8000. If Docker is using port
> 8000, either stop Docker first OR run only the pytest suite while Docker
> is running.

### 9.1 — Python Unit Tests (21 tests)

```powershell
# Create virtual env and install test deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Run tests with coverage (development mode, no admin auth enforcement)
$env:APP_ENV = "development"
$env:ADMIN_AUTH_ENABLED = "false"
pytest -v --cov=app --cov-report=term-missing

# Expected: 21 passed, coverage >= 70%
```

### 9.2 — Lint Check

```powershell
ruff check app.py tests/
# Expected: All checks passed! (no violations)
```

### 9.3 — E2E Runtime Smoke Test

```powershell
# Stop Docker first if using port 8000
docker compose -f docker-compose.yml -f docker-compose.staging.yml down

python scripts_e2e_runtime_smoke.py
# Expected: "E2E runtime smoke PASSED"
```

This script exercises the full governance flow over real HTTP:
- Health check
- Role submission
- Governed compile
- Trust ledger verification
- Execution verification
- Audit export

### 9.4 — Production Readiness Check

```powershell
python scripts_production_readiness_check.py
# Expected: "Production readiness check PASSED"
```

This script validates production-mode security invariants:
- Admin endpoints deny without Bearer token (401)
- Admin endpoints allow with correct Bearer token
- Deterministic compile + pack verification (signature + hash match)
- Signed export contains correct execution metadata
- Audit export create + download works
- Metrics endpoint includes threshold recommendations

### 9.5 — Frontend TypeScript Build Check

```powershell
cd Frontend
npm install
npm run build
cd ..
# Expected: Build succeeds with no TypeScript errors
# (npm run build runs: tsc --noEmit && vite build)
```

### 9.6 — Bridge Syntax Check

```powershell
node --check backend-ui-bridge/server.js
# Expected: No output (clean exit = success)
```

**Checkpoint 9:** All automated tests pass.

---

## PHASE 10 — CUSTOMER ONBOARDING PROCESS VALIDATION

The customer onboarding flow for a NEW customer follows this sequence:

### 10.1 — Onboarding File Sequence

| Step | Action | File/Script |
|------|--------|-------------|
| 1 | Copy config + manifest templates | `customer-config/_template/` -> `customer-config/<customer>/` |
| 2 | Fill in customer Azure IDs | Edit `customer-config/<customer>/config.env` |
| 3 | Create Key Vault secrets | Follow `customer-config/<customer>/keyvault-secrets-manifest.md` (5 secrets) |
| 4 | Pull secrets to local | `scripts/pull-keyvault-secrets.ps1 -Customer <customer>` |
| 5 | Start staging stack | `docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build` |
| 6 | Validate all integrations | Follow Phases 4-8 of this guide |
| 7 | Deploy to Azure | Follow `VENDORLOGIC_DEPLOYMENT_GUIDE.md` |

### 10.2 — Verify the Template Is Complete

```powershell
Get-Content customer-config\_template\config.env
# All values should be REPLACE_WITH_* placeholders

Get-Content customer-config\_template\keyvault-secrets-manifest.md
# Should list all 5 secrets with REPLACE_WITH_* vault name
```

### 10.3 — Verify Vendorlogic Config Is Filled In

```powershell
Get-Content customer-config\vendorlogic\config.env
# All values should be real UUIDs (no REPLACE_WITH_* remaining)

Select-String "REPLACE_WITH" customer-config\vendorlogic\config.env
# Expected: NO matches (empty output)
```

### 10.4 — Verify Pull Script Customer Selection

Both pull scripts accept a `--customer` / `-Customer` parameter to select which
customer config to use. They default to `vendorlogic` if not specified.

```powershell
# Windows — these are equivalent:
.\scripts\pull-keyvault-secrets.ps1                          # defaults to vendorlogic
.\scripts\pull-keyvault-secrets.ps1 -Customer vendorlogic    # explicit
$env:DIIAC_CUSTOMER = "vendorlogic"; .\scripts\pull-keyvault-secrets.ps1  # env var

# Mac/Linux/WSL — these are equivalent:
bash scripts/pull-keyvault-secrets.sh                         # defaults to vendorlogic
bash scripts/pull-keyvault-secrets.sh --customer vendorlogic  # explicit
DIIAC_CUSTOMER=vendorlogic bash scripts/pull-keyvault-secrets.sh  # env var
```

For a new customer (e.g., ACME Corp):
```powershell
# 1. Copy templates
Copy-Item -Recurse customer-config\_template customer-config\acmecorp

# 2. Fill in config.env and keyvault-secrets-manifest.md with real values

# 3. Pull secrets
.\scripts\pull-keyvault-secrets.ps1 -Customer acmecorp
```

If the customer config directory doesn't exist, the script will fail with a
clear error message pointing to the template.

**Checkpoint 10:** Customer onboarding flow validated — template, config, secrets, build, verify.

---

## DEBUGGING APPROACH — Change Tracking

When debugging issues, follow this discipline:

1. **Before any change:** Note the exact error message and which phase/step failed
2. **Make ONE change at a time** — never batch multiple fixes
3. **After each change:** Re-run ONLY the specific failing step to confirm it passes
4. **Record each change:**

```
| # | File Changed | What Changed | Why | Result |
|---|-------------|-------------|-----|--------|
| 1 | .env | Fixed OPENAI_API_KEY value | Was empty | Phase 7.2 now passes |
| 2 | ... | ... | ... | ... |
```

5. **If a fix breaks something else:** Revert it and try a different approach
6. **After all fixes:** Re-run the FULL sequence (Phases 4-9) end-to-end

---

## QUICK REFERENCE — Ports and URLs

| Service | URL | Auth |
|---------|-----|------|
| Frontend | http://localhost:5173 | Entra SSO (MSAL) |
| Bridge | http://localhost:3001 | Entra JWT (RS256) |
| Runtime | http://localhost:8000 | None (health), Bearer token (admin) |

## QUICK REFERENCE — Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base compose (dev defaults) |
| `docker-compose.staging.yml` | Staging overrides (Entra + real LLM + signing key) |
| `scripts/pull-keyvault-secrets.ps1` | Pull secrets from Azure Key Vault (Windows) |
| `scripts/pull-keyvault-secrets.sh` | Pull secrets from Azure Key Vault (Mac/Linux/WSL) |
| `customer-config/vendorlogic/config.env` | Vendorlogic public IDs (safe to commit) |
| `customer-config/_template/config.env` | Template for new customers |
| `.env` | Generated secrets (NEVER commit) |
| `.secrets/signing_key.pem` | Ed25519 key (NEVER commit) |
| `app.py` | Python governance runtime |
| `backend-ui-bridge/server.js` | Node.js bridge (API proxy, LLM orchestration) |
| `backend-ui-bridge/auth/entra.js` | Entra JWT validation (RS256 + HS256) |
| `backend-ui-bridge/auth/rbac.js` | RBAC middleware (role enforcement) |
| `backend-ui-bridge/llm-ingestion/providers/openai.js` | ChatGPT provider (OpenAI SDK, gpt-4o-mini) |
| `backend-ui-bridge/llm-ingestion/providers/copilot.js` | Copilot provider (OpenAI SDK -> Azure AI inference, gpt-4o) |
| `backend-ui-bridge/llm-ingestion/ingestRouter.js` | LLM ingestion audit endpoint (mounted at /api/ingest) |
| `Frontend/src/auth/authConfig.ts` | MSAL configuration (Entra OIDC + PKCE) |
| `Frontend/src/auth/roleMapping.ts` | Entra group -> DIIaC role mapping |
| `scripts_e2e_runtime_smoke.py` | E2E smoke tests |
| `scripts_production_readiness_check.py` | Production readiness validation |

## QUICK REFERENCE — LLM Provider Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           Frontend (React/Vite)          │
                    │  Provider selector: ChatGPT | Copilot    │
                    └──────────────┬───────────────────────────┘
                                   │ POST { provider: "Copilot" }
                    ┌──────────────▼───────────────────────────┐
                    │      Bridge (server.js) generateAI()      │
                    │                                           │
                    │  if provider === "ChatGPT":               │
                    │    → openai client (OPENAI_API_KEY)       │
                    │    → model: gpt-4o-mini                   │
                    │    → endpoint: api.openai.com             │
                    │                                           │
                    │  if provider === "Copilot":               │
                    │    → copilotClient (GITHUB_TOKEN)         │
                    │    → model: gpt-4o                        │
                    │    → endpoint: models.inference.ai.azure  │
                    └──────────────┬───────────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────────┐
                    │   Governance Runtime (app.py, port 8000)  │
                    │   Deterministic compile, signing, ledger  │
                    └──────────────────────────────────────────┘
```

## QUICK REFERENCE — Expected Test Results

| Test | Expected |
|------|----------|
| `pytest -v` | 21 passed |
| `pytest --cov=app` | Coverage >= 70% |
| `ruff check app.py tests/` | All checks passed |
| `scripts_e2e_runtime_smoke.py` | "E2E runtime smoke PASSED" |
| `scripts_production_readiness_check.py` | "Production readiness check PASSED" |
| `npm run build` (Frontend) | Build succeeds (tsc + vite) |
| `node --check server.js` (Bridge) | Clean exit |

---

## Verification Checklist — How to Confirm Everything Works

After completing all phases, this is the definitive checklist:

- [ ] `.env` generated from Key Vault with real values (Phase 1)
- [ ] `.secrets/signing_key.pem` exists with valid PEM header (Phase 1)
- [ ] `GITHUB_TOKEN` populated for Copilot provider (Phase 1, recommended)
- [ ] Entra app registration verified with localhost redirect URI (Phase 2)
- [ ] All 3 Docker containers running (Phase 3)
- [ ] `/health` returns OK (Phase 4.1)
- [ ] `/admin/health` returns `key_mode: "configured"` (Phase 4.2)
- [ ] Admin auth denies without token — 401 (Phase 4.3)
- [ ] 8 business profiles loaded (Phase 4.4)
- [ ] Governed compile returns execution_id (Phase 5.2)
- [ ] Execution verified on trust ledger — VERIFIABLE (Phase 5.3)
- [ ] Signed export has Ed25519 signature (Phase 5.5)
- [ ] Bridge healthy and connected to runtime (Phase 6)
- [ ] ChatGPT provider configured with real OpenAI key (Phase 7)
- [ ] Copilot provider configured with GitHub token (Phase 7, if available)
- [ ] Frontend loads at localhost:5173 (Phase 8.1)
- [ ] Entra SSO login works (Phase 8.2)
- [ ] Provider selector works for both ChatGPT and Copilot (Phase 8.5)
- [ ] 21 pytest tests pass with >= 70% coverage (Phase 9.1)
- [ ] Ruff lint passes (Phase 9.2)
- [ ] E2E smoke test passes (Phase 9.3)
- [ ] Production readiness check passes (Phase 9.4)
- [ ] Frontend TypeScript build succeeds (Phase 9.5)
- [ ] Bridge syntax check passes (Phase 9.6)
- [ ] Customer onboarding template valid (Phase 10)
