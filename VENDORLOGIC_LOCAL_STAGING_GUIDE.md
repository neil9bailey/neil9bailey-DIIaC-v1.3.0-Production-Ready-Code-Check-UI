# DIIaC v1.2.0 — Vendorlogic Local Docker Desktop Staging Guide

**Audience:** Vendorlogic — first customer
**Platform:** Local machine (Windows / Mac / Linux) + Docker Desktop
**Secrets:** Azure Key Vault (`kv-diiac-vendorlogic`)
**Auth:** Vendorlogic Azure Entra ID tenant

---

## What this gives you

A fully production-equivalent DIIaC stack running locally:

```
Your Machine (Docker Desktop)
├── governance-runtime      :8000   ← Python/Flask, signing key from Key Vault
├── backend-ui-bridge       :3001   ← Node/Express, Entra RS256 JWT validation
└── frontend                :5173   ← React/Vite, MSAL Entra login
        │
        └── secrets from ──► Azure Key Vault (kv-diiac-vendorlogic)
        └── auth via ────────► Vendorlogic Entra ID tenant
```

No LLM stub — real OpenAI key. Admin auth enforced. Entra SSO active.
This is how production will behave, running locally.

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| Azure CLI | https://learn.microsoft.com/cli/azure/install-azure-cli |
| Git | https://git-scm.com |
| OpenSSL | Included on Mac/Linux. Windows: Git Bash or WSL |

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

## Step 2 — Configure your Vendorlogic IDs in the pull script

Open `scripts/pull-keyvault-secrets.sh` (Mac/Linux/WSL) **or**
`scripts/pull-keyvault-secrets.ps1` (Windows PowerShell).

Fill in your Vendorlogic values at the top of the script:

```bash
KV_NAME="kv-diiac-vendorlogic"          # Your Key Vault name
ENTRA_TENANT_ID=""                        # Auto-detected if empty
ENTRA_API_APP_ID="<DIIaC-API client_id>" # From Entra App Registration
ENTRA_UI_APP_ID="<DIIaC-UI client_id>"   # From Entra App Registration
ENTRA_ADMIN_GROUP_ID="<DIIaC-Admins OID>"
ENTRA_USER_GROUP_ID="<DIIaC-Users OID>"
```

**Where to find these values:**

```bash
# Tenant ID
az account show --query tenantId -o tsv

# App registration client IDs
az ad app list --display-name "DIIaC-API-Vendorlogic" --query "[].appId" -o tsv
az ad app list --display-name "DIIaC-UI-Vendorlogic" --query "[].appId" -o tsv

# Group object IDs
az ad group show --group "DIIaC-Admins" --query id -o tsv
az ad group show --group "DIIaC-Users" --query id -o tsv
```

---

## Step 3 — Pull secrets from Azure Key Vault

**Mac / Linux / WSL:**
```bash
bash scripts/pull-keyvault-secrets.sh
```

**Windows PowerShell:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\pull-keyvault-secrets.ps1
```

What this does:
- Runs `az login` if you're not already logged in
- Pulls `diiac-admin-api-token` and `diiac-openai-api-key` → writes to `.env`
- Pulls `diiac-signing-private-key-pem` → writes to `.secrets/signing_key.pem`
- Builds all `ENTRA_*` and `VITE_ENTRA_*` vars from your configured IDs

Expected output:
```
✓ Logged in as: you@vendorlogic.com
✓ Key Vault found: kv-diiac-vendorlogic
✓ Signing key → .secrets/signing_key.pem
✓ ADMIN_API_TOKEN retrieved (64 chars)
✓ OPENAI_API_KEY retrieved
✓ .env written

Next step:
  docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

Verify the outputs:
```bash
# Check .env exists and has no placeholder values
grep "ADMIN_API_TOKEN" .env   # Should show a 64-char hex string
grep "OPENAI_API_KEY" .env    # Should show sk-...

# Check signing key is a valid PEM
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

## Step 5 — Start the full stack

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

What happens:
1. Docker builds the bridge and frontend images (~3–5 minutes first time)
2. Python runtime installs deps and starts on port 8000
3. Bridge starts on port 3001 and connects to the runtime
4. Frontend Vite dev server starts on port 5173

Watch the logs — wait until you see all three services healthy:
```
governance-runtime  | * Running on all addresses (0.0.0.0)
governance-runtime  | * Running on http://127.0.0.1:8000
backend-ui-bridge   | DIIaC Bridge listening on port 3001
frontend            | VITE v7.x.x  ready in Xms
frontend            | ➜  Local:   http://localhost:5173/
```

**Tip:** Run in detached mode after first build:
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
docker compose logs -f   # follow logs
```

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

## Re-pulling secrets (after rotation or first run)

Simply re-run the pull script — it overwrites `.env` and `.secrets/signing_key.pem`:

```bash
bash scripts/pull-keyvault-secrets.sh
# Then restart:
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

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

```bash
# Check the file exists and is non-empty
ls -la .secrets/signing_key.pem
head -1 .secrets/signing_key.pem   # Must show: -----BEGIN PRIVATE KEY-----

# Check Docker can see it — the compose override bind-mounts it as:
# .secrets/signing_key.pem → /run/secrets/signing_key
docker compose exec governance-runtime cat /run/secrets/signing_key | head -1
```

If the file is missing, re-run `scripts/pull-keyvault-secrets.sh`.

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

### Windows: PEM line ending issues

The PowerShell script writes the PEM with Unix line endings (`LF` only).
If you edited `.secrets/signing_key.pem` in Notepad and it now has CRLF
endings, the cryptography library will reject it.

Fix: re-run `.\scripts\pull-keyvault-secrets.ps1` — it always writes LF.

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
