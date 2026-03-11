# DIIaC — Vendorlogic Customer Instance

| Field | Value |
|-------|-------|
| **Customer** | Vendorlogic |
| **Instance ID** | `vendorlogic-prod` |
| **Platform version** | DIIaC v1.2.0 (locked) |
| **Platform repo** | `neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check` @ `v1.2.0` |
| **Instance repo** | `neil9bailey/DIIaC-Vendorlogic` |
| **Azure Tenant** | `1384b1c5-2bae-45a1-a4b4-e94e3315eb41` |
| **Key Vault** | `kv-diiac-vendorlogic` (uksouth) |
| **Created** | 2026-03-04 |

---

## What this instance contains

```
DIIaC-Vendorlogic/
├── [all platform files from v1.2.0 — unchanged]
│
├── customer-config/vendorlogic/
│   ├── config.env                    ← Vendorlogic public IDs (safe to commit)
│   ├── keyvault-secrets-manifest.md  ← What secrets live in Key Vault
│   └── INSTANCE_README.md            ← This file
│
├── scripts/
│   ├── pull-keyvault-secrets.sh      ← Pre-filled with Vendorlogic IDs
│   └── pull-keyvault-secrets.ps1     ← Pre-filled with Vendorlogic IDs
│
├── docker-compose.staging.yml        ← Staging override (Entra auth, real LLM)
│
├── VENDORLOGIC_LOCAL_STAGING_GUIDE.md
└── VENDORLOGIC_DEPLOYMENT_GUIDE.md
```

---

## Quick start — local Docker Desktop staging

```bash
# 1. Clone this instance repo
git clone https://github.com/neil9bailey/DIIaC-Vendorlogic.git
cd DIIaC-Vendorlogic

# 2. Pull secrets from Azure Key Vault (az login required)
bash scripts/pull-keyvault-secrets.sh
# or on Windows: .\scripts\pull-keyvault-secrets.ps1

# 3. Start the full stack
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build

# 4. Open: http://localhost:5173
```

Full guide: `VENDORLOGIC_LOCAL_STAGING_GUIDE.md`

---

## Entra ID configuration

| App | Display Name | Client ID | Purpose |
|-----|-------------|-----------|---------|
| API | `DIIaC-API-Vendorlogic` | `b726558d-f1c6-48f7-8a3d-72d5db818d0f` | Bridge RS256 JWT validation |
| UI | `DIIaC-UI-Vendorlogic` | `b726558d-f1c6-48f7-8a3d-72d5db818d0f` | Frontend MSAL SPA |

| Group | Display Name | Object ID | DIIaC Role |
|-------|-------------|-----------|------------|
| Admins | `DIIaC-Admins` | `81786818-de16-4115-b061-92fce74b00bd` | `admin` |
| Users | `DIIaC-Users` | `9c7dd0d4-5b44-4811-b167-e52df21092d8` | `standard` |

---

## Receiving platform updates (v1.3.0)

When DIIaC v1.3.0 is released:

```bash
# In this instance repo:
git remote add platform https://github.com/neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check.git
git fetch platform
git diff HEAD platform/main -- app.py   # Review what changed in the runtime
git merge platform/main                 # Merge platform changes
# Resolve any conflicts in customer-config/ files
git push origin main
```

Customer-specific files (`customer-config/vendorlogic/`, pull scripts,
Vendorlogic guides) will not conflict with platform changes as long as
platform code files (app.py, bridge, frontend) are not modified in this repo.

---

## Support contact

Platform maintainer: neil9bailey — via GitHub issues on the platform repo.
