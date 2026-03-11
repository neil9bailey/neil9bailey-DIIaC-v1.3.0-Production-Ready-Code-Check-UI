# DIIaC v1.2.0 — Vendorlogic Local Docker Desktop Staging Guide

**Audience:** Vendorlogic — first customer
**Platform:** Local machine (Windows / Mac / Linux) + Docker Desktop
**Secrets:** Azure Key Vault `kv-diiac-vendorlogic` (active) — run `scripts/pull-keyvault-secrets.sh` before starting
**Auth:** Vendorlogic Azure Entra ID tenant

---

## What this gives you

A fully production-equivalent DIIaC stack running locally:

```
Your Machine (Docker Desktop)
├── governance-runtime      :8000   ← Python/Flask, signing key from .secrets/
├── backend-ui-bridge       :3001   ← Node/Express, Entra RS256 JWT validation
└── frontend                :5173   ← React/Vite, MSAL Entra login
        │
        └── secrets from ──► Key Vault pull script → .env + .secrets/signing_key.pem
        └── auth via ────────► Vendorlogic Entra ID tenant
```

No LLM stub — real OpenAI key. Admin auth enforced. Entra SSO active.
This is how production will behave, running locally.

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| Git | https://git-scm.com |
| Azure CLI | https://learn.microsoft.com/cli/azure/install-azure-cli |
| `Key Vault Secrets User` role on `kv-diiac-vendorlogic` | Assigned by Azure admin — see `customer-config/vendorlogic/keyvault-secrets-manifest.md` |

Docker Desktop must be running before you begin.

---

## Step 1 — Clone and check out v1.2.0

```bash
git clone https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git diiac
cd diiac
git checkout v1.2.0
```

Verify you're on the locked tag:
```bash
git describe --tags
# Should output: v1.2.0
```

---

## Step 2 — Start the stack (single command)

This one command pulls all secrets from Key Vault and starts the full Docker stack:

**Windows PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-staging.ps1
```

**Mac / Linux / WSL:**
```bash
bash start-staging.sh
```

To start in the background (detached):
```powershell
.\start-staging.ps1 -Detach       # Windows
bash start-staging.sh --detach    # Mac/Linux/WSL
```

To restart without rebuilding images (subsequent starts after first build):
```powershell
.\start-staging.ps1 -NoBuild      # Windows
bash start-staging.sh --no-build  # Mac/Linux/WSL
```

> **Windows requirement:** Windows PowerShell 5.1 (built into Windows 10/11) or PowerShell 7+.
> Do **not** run in Command Prompt (`cmd.exe`).

What the launcher does:
1. Confirms Docker Desktop is running
2. Connects to `kv-diiac-vendorlogic` via `az login` and pulls all secrets
3. Verifies `.env` and `.secrets/signing_key.pem` are valid before starting
4. Runs `docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build`

Expected output (Windows):
```
DIIaC v1.2.0 -- Local Staging Launcher
========================================

-- Step 1 : Checking Docker Desktop
[OK]   Docker Desktop is running

-- Step 2 : Pulling secrets from Azure Key Vault
[OK]   Logged in as: you@vendorlogic.io
[OK]   Key Vault found: kv-diiac-vendorlogic
[OK]   .secrets\ directory ready
[OK]   Signing key -> .secrets\signing_key.pem
[OK]   ADMIN_API_TOKEN retrieved (64 chars)
[OK]   OPENAI_API_KEY retrieved
[OK]   .env written

-- Step 3 : Verifying outputs
[OK]   .env present
[OK]   .secrets\signing_key.pem valid

-- Step 4 : Starting DIIaC stack
[... docker compose build and startup output ...]
```

### Running the pull script standalone

If you only need to refresh secrets without restarting the stack:

```powershell
.\start-staging.ps1 -SecretsOnly  # Windows
bash start-staging.sh --secrets-only  # Mac/Linux/WSL
```

Or call the pull script directly:

```powershell
.\scripts\pull-keyvault-secrets.ps1   # Windows
bash scripts/pull-keyvault-secrets.sh # Mac/Linux/WSL
```

---

## Step 3 — Verify secrets are in place

```bash
# Check .env has real values (not placeholders)
grep "ADMIN_API_TOKEN" .env   # Should show a 64-char hex string
grep "OPENAI_API_KEY" .env    # Should show sk-...

# Check signing key is valid
head -1 .secrets/signing_key.pem
# Should show: -----BEGIN PRIVATE KEY-----
```

---

## Step 4 — Add localhost redirect URIs to Entra App Registration

The frontend needs `http://localhost:5173/auth/callback` registered as an
allowed redirect URI. Do this once in the Azure Portal.

1. Go to **portal.azure.com → Entra ID → App registrations**
2. Open **DIIaC-UI-Vendorlogic**
3. Select **Authentication**
4. Under **Web** → **Redirect URIs**, add:
   - `http://localhost:5173/auth/callback`
   - `http://localhost:5173` (for post-logout redirect)
5. Click **Save**

> This does not affect any production settings — localhost URIs are only
> used when the app is accessed from localhost.

---

## Step 5 — Stack startup (handled by launcher)

If you used `.\start-staging.ps1` or `bash start-staging.sh` in Step 2,
the stack is already starting. Skip to Step 6.

If you need to start the stack manually (e.g. after stopping it):

**Windows:**
```powershell
.\start-staging.ps1 -NoBuild        # restart without rebuild
.\start-staging.ps1 -NoBuild -Detach  # restart in background
```

**Mac / Linux / WSL:**
```bash
bash start-staging.sh --no-build
bash start-staging.sh --no-build --detach
```

Or directly with docker compose:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
docker compose logs -f
```

Wait until all three services are healthy:
```
governance-runtime  | * Running on all addresses (0.0.0.0)
governance-runtime  | * Running on http://127.0.0.1:8000
backend-ui-bridge   | DIIaC Bridge listening on port 3001
frontend            | VITE v7.x.x  ready in Xms
frontend            | ➜  Local:   http://localhost:5173/
```

> First build takes 3–5 minutes (Docker pulls and compiles images). Subsequent starts are fast.

---

## Step 6 — Verify the stack

### Health check (no auth needed)
```bash
curl http://localhost:8000/health
```
Expected:
```json
{"status": "OK", "readiness": {"overall_ready": true, ...}}
```

### Admin health (auth required)
```bash
# Get token from .env
ADMIN_TOKEN=$(grep ADMIN_API_TOKEN .env | cut -d= -f2)

curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/health
```
Expected:
```json
{
  "status": "OK",
  "signing_enabled": true,
  "key_mode": "configured",
  "strict_deterministic_mode": true
}
```

If `key_mode` is `ephemeral` → the signing key didn't load. See Troubleshooting.

### Business profiles
```bash
curl http://localhost:8000/api/business-profiles | python3 -m json.tool
# Should list 8 sector profiles
```

### Admin metrics
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/admin/metrics | python3 -m json.tool
# health_status: "OK", alerts: []
```

---

## Step 7 — First governed compile

```bash
CONTEXT_ID="vendorlogic-staging-$(date +%s)"

# 1. Ingest CTO role input
curl -s -X POST http://localhost:8000/api/human-input/role \
  -H "Content-Type: application/json" \
  -d "{
    \"execution_context_id\": \"$CONTEXT_ID\",
    \"role\": \"CTO\",
    \"domain\": \"Cloud Infrastructure Procurement\",
    \"assertions\": [
      \"Azure-primary multi-cloud strategy\",
      \"Zero-trust security architecture\",
      \"UK data residency mandatory\"
    ],
    \"non_negotiables\": [
      \"Microsoft Entra ID integration\",
      \"ISO 27001 compliance\",
      \"99.9 SLA\"
    ],
    \"risk_flags\": [
      \"Single-vendor lock-in\",
      \"Shadow IT proliferation\"
    ],
    \"evidence_refs\": [
      \"REF-001: Board technology mandate Q1 2026\"
    ]
  }" | python3 -m json.tool

# 2. Governed compile
RESULT=$(curl -s -X POST http://localhost:8000/api/governed-compile \
  -H "Content-Type: application/json" \
  -d "{
    \"execution_context_id\": \"$CONTEXT_ID\",
    \"schema_id\": \"it_enterprise_governance_v1\",
    \"profile_id\": \"it_enterprise\",
    \"reasoning_level\": \"strategic\",
    \"policy_level\": \"board\",
    \"governance_modes\": [\"strict\", \"hitl\"]
  }")

echo $RESULT | python3 -m json.tool
EXEC_ID=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")
echo "Execution ID: $EXEC_ID"
```

### Verify the compile output

```bash
# Ledger verification
curl -s http://localhost:8000/verify/execution/$EXEC_ID | python3 -m json.tool
# status: VERIFIABLE, ledger_match: true

# Signed export metadata (Ed25519 signature)
curl -s http://localhost:8000/decision-pack/$EXEC_ID/export-signed | python3 -m json.tool
# signature_alg: Ed25519, signing_key_id should be non-empty

# Merkle tree
curl -s http://localhost:8000/executions/$EXEC_ID/merkle | python3 -m json.tool
```

---

## Step 8 — Open the UI

Open: **http://localhost:5173**

If Entra ID is configured, you'll be redirected to the Microsoft login page.
Sign in with your Vendorlogic credentials.

Once logged in:
- Admin users (in DIIaC-Admins group) see the full Admin Console panel
- Standard users (in DIIaC-Users group) see the governance workflow panels

> If MSAL login isn't working yet, check Step 4 (redirect URIs) and that
> `VITE_ENTRA_CLIENT_ID` in `.env` matches your DIIaC-UI app registration.

---

## Step 9 — Run the full test suite

```bash
# Python tests (21 tests)
pip3 install -r requirements-dev.txt
APP_ENV=development ADMIN_AUTH_ENABLED=false pytest -v

# E2E smoke test (against running stack)
python3 scripts_e2e_runtime_smoke.py

# Production readiness check (against running stack with admin auth)
ADMIN_TOKEN=$(grep ADMIN_API_TOKEN .env | cut -d= -f2) \
  python3 scripts_production_readiness_check.py
```

All 21 pytest tests and all smoke/readiness checks must pass before promoting
to Azure production.

---

## Stopping and restarting

```bash
# Stop (keeps volumes/data)
docker compose -f docker-compose.yml -f docker-compose.staging.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker-compose.yml -f docker-compose.staging.yml down -v

# Restart (no rebuild)
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Rebuild a specific service after code change
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build backend-ui-bridge
```

---

## Refreshing secrets

Re-run the launcher with `-NoBuild` to pull fresh secrets and restart without rebuilding:

**Windows:**
```powershell
.\start-staging.ps1 -NoBuild -Detach
```

**Mac / Linux / WSL:**
```bash
bash start-staging.sh --no-build --detach
```

To pull secrets only (without restarting the running stack):

```powershell
.\start-staging.ps1 -SecretsOnly        # Windows
bash start-staging.sh --secrets-only    # Mac/Linux/WSL
```

Then restart the affected service:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d governance-runtime
```

For rotation procedures see `customer-config/vendorlogic/keyvault-secrets-manifest.md`.

---

## Port reference

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:5173 | React UI, MSAL login |
| Bridge | http://localhost:3001 | API proxy, Entra JWT validation |
| Runtime | http://localhost:8000 | Governance engine, admin auth |
| Runtime health | http://localhost:8000/health | No auth required |
| Admin health | http://localhost:8000/admin/health | Bearer token required |

---

## Troubleshooting

### `key_mode: ephemeral` in /admin/health

The signing key didn't load from `.secrets/signing_key.pem`.

```powershell
# Windows — check file exists and is non-empty
Get-Content .secrets\signing_key.pem | Select-Object -First 1
# Must print: -----BEGIN PRIVATE KEY-----
```

```bash
# Mac/Linux — check the file exists and is non-empty
ls -la .secrets/signing_key.pem
head -1 .secrets/signing_key.pem   # Must show: -----BEGIN PRIVATE KEY-----

# Check Docker can see it — the compose override bind-mounts it as:
# .secrets/signing_key.pem → /run/secrets/signing_key
docker compose exec governance-runtime cat /run/secrets/signing_key | head -1
```

If the file is missing or empty, re-run the pull script to restore it from Key Vault:

```powershell
# Windows
.\scripts\pull-keyvault-secrets.ps1
```

```bash
# Mac/Linux
bash scripts/pull-keyvault-secrets.sh
```

If the file is present and non-empty but `key_mode` is still `ephemeral`, the key failed to
load silently — see [governance-runtime crash-loops with `ValueError`](#governance-runtime-crash-loops-with-valueerror-could-not-deserialize-key-data) below.

### `admin_auth_required` — 401 on /admin/* endpoints

```bash
# Verify ADMIN_API_TOKEN in .env
grep ADMIN_API_TOKEN .env

# Verify runtime received it
docker compose exec governance-runtime env | grep ADMIN_API_TOKEN
```

### Bridge not connecting to runtime

```bash
docker compose logs backend-ui-bridge | tail -20
# Should show: Connected to governance-runtime

# Check runtime is responding
docker compose exec backend-ui-bridge wget -qO- http://governance-runtime:8000/health
```

### MSAL redirect loop / login fails

1. Confirm `http://localhost:5173/auth/callback` is in the DIIaC-UI app registration redirect URIs (Step 4).
2. Check `VITE_ENTRA_CLIENT_ID` in `.env` matches the DIIaC-UI app registration.
3. Check browser console for specific MSAL errors.

### Port already in use

```bash
# Override in .env:
RUNTIME_HOST_PORT=8001
BRIDGE_HOST_PORT=3002
FRONTEND_HOST_PORT=5174
```

### Windows: `pull-keyvault-secrets.ps1` script errors

The script requires **Windows PowerShell 5.1** (shipped with Windows 10/11).
The following errors were observed and resolved during initial setup — documented here
so they can be identified and resolved quickly if encountered again.

---

**Error: `Unexpected token '??'`**

```
Unexpected token '??' in expression or statement.
```

Cause: The `??` null-coalescing operator requires PowerShell 7+.
The script uses a PS 5.1-compatible `Nvl` helper function instead.
If you see this, you are running an older script version — pull the latest:

```powershell
git pull
```

---

**Error: `Join-Path: A positional parameter cannot be found`**

```
Join-Path : A positional parameter cannot be found that accepts argument '...'
```

Cause: `Join-Path` in PS 5.1 accepts only two path arguments at a time (PS 7+ accepts more).
The script now chains `Join-Path` calls. Pull the latest if you see this:

```powershell
git pull
```

---

**Error: `WriteAllBytes: Access to the path is denied`**

```
Exception calling "WriteAllBytes" with "2" argument(s): "Access to the path
'...\signing_key.pem' is denied."
```

Cause: `.secrets\signing_key.pem` exists from a previous run and Windows has locked
it (read-only attribute or ACL restriction). The script now deletes the file before
writing, which bypasses both.

If you still see this on a fresh pull, delete the file manually first:

```powershell
Remove-Item -Force ".secrets\signing_key.pem"
.\scripts\pull-keyvault-secrets.ps1
```

If `Remove-Item -Force` itself fails (directory-level ACL), reset permissions:

```powershell
icacls ".secrets" /reset /T
.\scripts\pull-keyvault-secrets.ps1
```

---

### Windows: PEM line ending issues

The PowerShell script writes the PEM with Unix line endings (`LF` only).
If you edited `.secrets/signing_key.pem` in Notepad and it now has CRLF
endings, the governance-runtime may reject it.

Fix: re-run `.\scripts\pull-keyvault-secrets.ps1` — it always writes LF.

---

### `governance-runtime` crash-loops with `ValueError: Could not deserialize key data`

**Symptom:** `governance-runtime-1` starts, installs packages, then crashes repeatedly:

```
ValueError: ('Could not deserialize key data. The data may be in an incorrect format...',
[<OpenSSLError(code=503841036, lib=60, reason=524556, reason_text=unsupported)>])
```

`frontend-1` and `backend-ui-bridge-1` remain up. Only `governance-runtime-1` loops.

**Root cause:** The Ed25519 private key stored in Key Vault is corrupt, incompatible with
OpenSSL 3.x, or the secret value is empty. This can happen if:

- The secret was never populated, or was overwritten with an empty value
- The key was generated by an older tool that produces explicit EC parameters
- A failed upload stored an empty file to Key Vault

**Diagnosis:**

```powershell
# 1. Check the local file looks valid
Get-Content .secrets\signing_key.pem | Select-Object -First 1
# Must print: -----BEGIN PRIVATE KEY-----
# If the file is empty or missing, the Key Vault secret is blank — see recovery below.

# 2. Check the Key Vault secret directly
az keyvault secret show --vault-name kv-diiac-vendorlogic `
  --name diiac-signing-private-key-pem --query "value" -o tsv | Select-Object -First 1
# Must print: -----BEGIN PRIVATE KEY-----
# Empty output = blank secret in Key Vault.
```

**Fix — regenerate and re-upload the signing key:**

> This generates a fresh Ed25519 key using Azure CLI's bundled Python (which has
> `cryptography` installed), uploads it to Key Vault, then re-pulls secrets.

```powershell
# Stop the stack first
docker compose -f docker-compose.yml -f docker-compose.staging.yml down

# Generate a fresh Ed25519 key using Azure CLI's bundled Python
& "C:\Program Files\Microsoft SDKs\Azure\CLI2\python.exe" -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives import serialization; key = Ed25519PrivateKey.generate(); print(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(), end='')" | Out-File -Encoding ascii -NoNewline new_ed25519_key.pem

# VERIFY before uploading — must show -----BEGIN PRIVATE KEY-----
Get-Content new_ed25519_key.pem

# Upload to Key Vault (only if the verify step above shows a valid PEM header)
az keyvault secret set `
  --vault-name kv-diiac-vendorlogic `
  --name diiac-signing-private-key-pem `
  --file new_ed25519_key.pem

# Delete the local copy
Remove-Item new_ed25519_key.pem

# Re-pull secrets and restart
.\start-staging.ps1
```

> **Important:** Always verify `Get-Content new_ed25519_key.pem` shows a valid PEM header
> before uploading. If the generation step fails silently, you will upload an empty value
> to Key Vault and the secret will need to be restored again.

**Expected healthy startup (governance-runtime):**

```
governance-runtime-1  | DIIaC Governance Engine — Deterministic R/P Enforcement Active
governance-runtime-1  |   Auth mode: entra_jwt_rs256
governance-runtime-1  |   Entra ID: ENABLED
```

Confirm key loaded correctly (not ephemeral):

```powershell
Invoke-RestMethod http://localhost:8000/admin/health `
  -Headers @{ Authorization = "Bearer $env:ADMIN_API_TOKEN" } | Select-Object key_mode
# Must print: key_mode: configured
```

---

### Slow first build

Docker must build the bridge and frontend images. On first run this can take
5–10 minutes depending on internet speed. Subsequent starts are fast (cached layers).

---

## What's committed vs what's local-only

| File | Committed | Notes |
|------|-----------|-------|
| `docker-compose.yml` | ✓ | Base compose — development defaults |
| `docker-compose.staging.yml` | ✓ | Staging override — safe to commit |
| `scripts/pull-keyvault-secrets.sh` | ✓ | No secrets in script |
| `scripts/pull-keyvault-secrets.ps1` | ✓ | No secrets in script |
| `.env` | ✗ | Generated locally, contains secrets |
| `.secrets/signing_key.pem` | ✗ | Generated locally, never commit |

`.gitignore` already covers `.env` and `.secrets/`.

---

## Next: Promote to Azure

When staging validation is complete, follow the Azure production deployment
path in `VENDORLOGIC_DEPLOYMENT_GUIDE.md` — either Docker Compose on an
Azure VM (Step 6A) or AKS (Step 6B). All secrets are already in Key Vault;
you simply switch the compute layer.
