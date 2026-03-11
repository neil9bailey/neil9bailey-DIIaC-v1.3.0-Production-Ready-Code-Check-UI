# DIIaC — Customer Instance Fork Model

## Overview

Each DIIaC customer deployment is an independent **customer instance repo**
forked from the **platform repo** at a locked version tag. The platform code
is never modified — only customer-specific configuration is added on top.

```
┌─────────────────────────────────────────────────────────────────┐
│  PLATFORM REPO                                                   │
│  neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check          │
│                                                                  │
│  ● Source of truth for all platform code                        │
│  ● Version-locked releases (v1.2.0, v1.3.0, ...)               │
│  ● No customer-specific config committed here                   │
└────────────────────────┬────────────────────────────────────────┘
                         │  fork at tag v1.2.0
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ DIIaC-       │  │ DIIaC-       │  │ DIIaC-       │
  │ Vendorlogic  │  │ Customer002  │  │ Customer003  │
  │              │  │              │  │              │
  │ + config.env │  │ + config.env │  │ + config.env │
  │ + pull script│  │ + pull script│  │ + pull script│
  │ @ v1.2.0     │  │ @ v1.2.0     │  │ @ v1.3.0     │
  └──────────────┘  └──────────────┘  └──────────────┘
  Customer 001      Customer 002      Customer 003
  (Vendorlogic)     (future)          (future, v1.3.0)
```

---

## What a customer instance repo contains

### Inherited from platform (never modified)

```
app.py                          ← Governance runtime — untouched
backend-ui-bridge/              ← Bridge — untouched
Frontend/                       ← React UI — untouched
contracts/business-profiles/    ← Sector profiles — can extend, not modify
docker-compose.yml              ← Base compose — untouched
requirements.txt                ← Python deps — untouched
openapi.yaml                    ← API spec — untouched
deploy/kubernetes/              ← K8s manifests — untouched (override via kustomize if needed)
```

### Added in customer instance

```
customer-config/<customer-name>/
├── config.env                  ← Public IDs: tenant, app registrations, groups
├── keyvault-secrets-manifest.md ← Which secrets exist in Key Vault (no values)
└── INSTANCE_README.md          ← Customer-specific notes and quick-start

scripts/
├── pull-keyvault-secrets.sh    ← Pre-filled with customer Key Vault name + Entra IDs
└── pull-keyvault-secrets.ps1   ← Same, Windows PowerShell

docker-compose.staging.yml      ← Staging override (admin auth, Entra, real LLM)

VENDORLOGIC_LOCAL_STAGING_GUIDE.md    ← (or CUSTOMER_LOCAL_STAGING_GUIDE.md)
VENDORLOGIC_DEPLOYMENT_GUIDE.md       ← (or CUSTOMER_DEPLOYMENT_GUIDE.md)
```

### Optionally extended in customer instance

```
contracts/business-profiles/
└── <customer>_profile_v1.json  ← Add new sector profiles specific to this customer

contracts/keys/
└── public_keys.json            ← Add customer's signing public key
```

---

## How to create a new customer instance

### Step 1 — Fork the platform repo at the target version tag

**Via GitHub UI:**
1. Go to `neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check`
2. Click **Fork** → name it `DIIaC-<CustomerName>` (e.g. `DIIaC-Vendorlogic`)
3. After forking, check out the locked tag locally:

```bash
git clone https://github.com/neil9bailey/DIIaC-<CustomerName>.git
cd DIIaC-<CustomerName>
git checkout v1.2.0
git checkout -b main        # work on main from this point
git push -u origin main
```

**Via CLI (if forking to a different org):**
```bash
git clone https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git DIIaC-<CustomerName>
cd DIIaC-<CustomerName>
git remote set-url origin https://github.com/<org>/DIIaC-<CustomerName>.git
git checkout v1.2.0 -b main
git push -u origin main
```

### Step 2 — Copy the customer config template

```bash
cp -r customer-config/_template customer-config/<customer-name>
```

Edit `customer-config/<customer-name>/config.env` — fill in all `REPLACE_WITH_*` values:

| Field | How to find it |
|-------|---------------|
| `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
| `ENTRA_API_APP_ID` | App registration client_id for the backend (DIIaC-API) |
| `ENTRA_UI_APP_ID` | App registration client_id for the frontend (DIIaC-UI) |
| `ENTRA_ADMIN_GROUP_ID` | `az ad group show --group "DIIaC-Admins" --query id -o tsv` |
| `ENTRA_STANDARD_GROUP_ID` | `az ad group show --group "DIIaC-Users" --query id -o tsv` |
| `KEY_VAULT_NAME` | The Azure Key Vault name for this customer |
| `AZURE_LOCATION` | Azure region (e.g. `uksouth`, `westeurope`, `eastus`) |

### Step 3 — Update the pull scripts

Edit `scripts/pull-keyvault-secrets.sh` and `.ps1`:

In the bash script, change the config path line:
```bash
CUSTOMER_CONFIG="$(cd "$(dirname "$0")/.." && pwd)/customer-config/<customer-name>/config.env"
```

In the PowerShell script:
```powershell
$configFile = Join-Path $repoRoot "customer-config" "<customer-name>" "config.env"
```

### Step 4 — Provision Azure resources

Follow `VENDORLOGIC_DEPLOYMENT_GUIDE.md` (or the equivalent customer guide)
Steps 1–5 to create the resource group, Key Vault, Entra app registrations,
and secrets.

### Step 5 — Create and populate Key Vault secrets

```bash
# Generate admin token
openssl rand -hex 32 | az keyvault secret set \
  --vault-name <kv-name> --name "diiac-admin-api-token" --value @-

# Generate signing key
openssl genpkey -algorithm ed25519 | az keyvault secret set \
  --vault-name <kv-name> --name "diiac-signing-private-key-pem" --value @-

# Store OpenAI key
az keyvault secret set --vault-name <kv-name> \
  --name "diiac-openai-api-key" --value "sk-..."
```

### Step 6 — Test locally

```bash
bash scripts/pull-keyvault-secrets.sh
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
curl http://localhost:8000/health
```

### Step 7 — Commit customer config to the instance repo

```bash
git add customer-config/<customer-name>/ scripts/ docker-compose.staging.yml
git commit -m "chore: configure <CustomerName> customer instance"
git push origin main
```

---

## Receiving platform updates

When a new platform version is released, update a customer instance with a
controlled merge.

```bash
# In the customer instance repo:

# Add platform as a remote (one-time)
git remote add platform https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git

# Fetch the new version tag
git fetch platform --tags

# Review what changed in core platform files
git diff HEAD platform/v1.3.0 -- app.py requirements.txt docker-compose.yml

# Review breaking changes in the release notes
git show platform/v1.3.0:RELEASE_NOTES_V1_3_0.md

# Merge into a branch for testing
git checkout -b upgrade/v1.3.0
git merge platform/v1.3.0

# Resolve any conflicts — customer-config/ files will rarely conflict
# since platform code doesn't touch that directory.

# Test thoroughly, then merge to main
git checkout main
git merge upgrade/v1.3.0
git push origin main
```

---

## Rules for customer instance repos

| Rule | Why |
|------|-----|
| **Never modify `app.py`** | Platform code divergence breaks upgrade path |
| **Never modify `backend-ui-bridge/server.js`** | Same reason |
| **Never modify `docker-compose.yml`** (base) | Use `docker-compose.staging.yml` override instead |
| **Never commit `.env` or `.secrets/`** | Contains secrets — `.gitignore` covers these |
| **Keep `customer-config/` additions additive** | Don't remove platform files from customer repos |
| **Sector profile additions go in `contracts/business-profiles/`** | Naming: `<customer>_<sector>_profile_v1.json` |
| **Tag customer instance releases** | e.g. `vendorlogic-v1.2.0-r1` — separate from platform tags |

---

## Customer instance registry

| Customer | Instance Repo | Platform Version | Status |
|----------|--------------|-----------------|--------|
| Vendorlogic | `neil9bailey/DIIaC-Vendorlogic` | v1.2.0 | Active — Customer 001 |
| *(future)* | `neil9bailey/DIIaC-<Customer002>` | v1.3.0 | Pending |

---

## Directory reference

```
DIIaC-v1.2.0-Production-Ready-Code-Check/
└── customer-config/
    ├── _template/                 ← Copy this for each new customer
    │   └── config.env             ← REPLACE_WITH_* placeholders
    └── vendorlogic/               ← Customer 001 — Vendorlogic
        ├── config.env             ← Pre-filled Vendorlogic IDs
        ├── keyvault-secrets-manifest.md
        └── INSTANCE_README.md
```
