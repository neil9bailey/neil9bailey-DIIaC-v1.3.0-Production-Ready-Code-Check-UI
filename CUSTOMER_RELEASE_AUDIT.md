# DIIaC v1.2.0 — Customer Release Audit

> **Purpose:** Documents what changes between the Vendorlogic dev repo (`DIIaC-v1.2.0-Production-Ready-Code-Check`)
> and the customer-facing locked release (`DIIaC-V1.2.0c-Production-Customer-Release`).
>
> Run `scripts/prepare-customer-release.sh` to apply all transformations automatically.

---

## Repo roles

| Repo | Purpose | Who touches it |
|------|---------|----------------|
| `DIIaC-v1.2.0-Production-Ready-Code-Check` | Vendorlogic active dev — Azure integration, KV completion, Vendorlogic staging | Vendorlogic team |
| `DIIaC-V1.2.0c-Production-Customer-Release` | Locked customer template — v1.2.0 snapshot, clean baseline, multi-customer deliverable | Read-only for customers; Vendorlogic updates on new releases |
| `DIIaC-V1.3.0c-Production-Ready-Codebase` | Next-gen headless/direct LLM version development | Vendorlogic team |

---

## Source code — changes needed for customer release

### 1. `Frontend/src/auth/authConfig.ts`

**Issue:** Hard-coded Vendorlogic Entra IDs as fallback defaults.

```ts
// DEV REPO (has Vendorlogic defaults — correct for internal staging):
const ENTRA_CLIENT_ID =
  import.meta.env.VITE_ENTRA_CLIENT_ID || "b726558d-f1c6-48f7-8a3d-72d5db818d0f";

const ENTRA_TENANT_ID =
  import.meta.env.VITE_ENTRA_TENANT_ID || "1384b1c5-2bae-45a1-a4b4-e94e3315eb41";
```

```ts
// CUSTOMER RELEASE (no defaults — forces customer to set their own values):
const ENTRA_CLIENT_ID =
  import.meta.env.VITE_ENTRA_CLIENT_ID || "";

const ENTRA_TENANT_ID =
  import.meta.env.VITE_ENTRA_TENANT_ID || "";
```

**Why:** A customer's frontend must not fall back to Vendorlogic's tenant. Empty string causes MSAL to surface a clear config error rather than silently connect to the wrong tenant.

---

### 2. `Frontend/src/auth/roleMapping.ts`

**Issue:** Default group map contains Vendorlogic group OIDs.

```ts
// DEV REPO:
const DEFAULT_GROUP_MAP: Record<string, GroupMapping> = {
  "81786818-de16-4115-b061-92fce74b00bd": { role: "admin" },
  "9c7dd0d4-5b44-4811-b167-e52df21092d8": { role: "standard" },
};
```

```ts
// CUSTOMER RELEASE:
const DEFAULT_GROUP_MAP: Record<string, GroupMapping> = {};
```

**Why:** If a customer doesn't set `VITE_ENTRA_GROUP_MAP`, everyone falls through to `viewer` role rather than accidentally matching Vendorlogic group OIDs.

---

### 3. `Frontend/.env`

**Issue:** Contains live Vendorlogic Entra IDs.

**Customer release version:** Replace with `REPLACE_WITH_*` placeholders. See `customer-config/_template/config.env` for the authoritative placeholder names.

```dotenv
VITE_API_BASE=http://localhost:3001

VITE_ENTRA_CLIENT_ID=REPLACE_WITH_UI_APP_CLIENT_ID
VITE_ENTRA_TENANT_ID=REPLACE_WITH_TENANT_ID
VITE_ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_ENTRA_GROUP_MAP={"REPLACE_WITH_ADMIN_GROUP_OID":{"role":"admin"},"REPLACE_WITH_STANDARD_GROUP_OID":{"role":"standard"}}
```

---

### 4. `.env.example`

**Issue:** Commented Vendorlogic tenant and app IDs appear as examples.

**Customer release version:** Replace all commented Vendorlogic IDs with `REPLACE_WITH_*` values so they function as true placeholders, not leaky examples.

---

### 5. `customer-config/` directory

**Dev repo structure:**
```
customer-config/
├── _template/        ← generic template (keep)
└── vendorlogic/      ← Vendorlogic's live config (EXCLUDE from customer release)
```

**Customer release structure:**
```
customer-config/
└── _template/        ← only the template; customer copies this to customer-config/<their-name>/
```

The `vendorlogic/` folder contains live Entra IDs, Key Vault name, and tenant details. It must not ship in a customer release.

---

### 6. `scripts/pull-keyvault-secrets.sh` / `.ps1`

**Issue:** Path to config is hard-coded to `customer-config/vendorlogic/config.env`.

**Customer release version:** Path references `customer-config/<CUSTOMER_ID>/config.env` where `CUSTOMER_ID` comes from a variable the customer sets, or the script prompts for it.

**Current line:**
```bash
CUSTOMER_CONFIG="$(cd "$(dirname "$0")/.." && pwd)/customer-config/vendorlogic/config.env"
```

**Customer release version:**
```bash
CUSTOMER_ID="${DIIAC_CUSTOMER_ID:-}"
if [ -z "$CUSTOMER_ID" ]; then
  echo "ERROR: Set DIIAC_CUSTOMER_ID env var to your customer-config folder name."
  echo "Example: DIIAC_CUSTOMER_ID=acme-corp bash scripts/pull-keyvault-secrets.sh"
  exit 1
fi
CUSTOMER_CONFIG="$(cd "$(dirname "$0")/.." && pwd)/customer-config/${CUSTOMER_ID}/config.env"
```

---

### 7. `openapi.yaml`

**Issue:** GitHub URL references `neil9bailey/DIIaC-v1.2.0-Production-Ready-Code-Check`.

**Customer release version:** Update to reference `neil9bailey/DIIaC-V1.2.0c-Production-Customer-Release`.

---

### 8. `deploy/kubernetes/*.yaml`

Images reference `ghcr.io/neil9bailey/...` — this is correct for the published release images and does not need to change.

---

## Documentation — include vs exclude

### Include in customer release

| File | Notes |
|------|-------|
| `GETTING_STARTED.md` | Primary onboarding — includes Phase A/B KV transition |
| `KEY_VAULT_TRANSITION.md` | Pre/post KV guide |
| `ENTRA_ID_SETUP_GUIDE.md` | Customer needs this to configure their tenant |
| `DEPLOYMENT_VALIDATION_RUNBOOK.md` | Post-deploy checks |
| `OFFLINE_VERIFIER_RUNBOOK.md` | Cryptographic verification |
| `ADMIN_CONSOLE_USER_GUIDE.md` | End-user guide |
| `DIIAC_UI_WORKFLOW_GUIDE.md` | End-user guide |
| `DIIAC_CRYPTOGRAPHIC_SPEC.md` | Technical reference |
| `DIIAC_CAPABILITIES_MATRIX.md` | Feature reference |
| `DIIAC_VISUAL_WORKFLOW_DIAGRAM.md` | Visual reference |
| `DIIAC_REAL_WORLD_E2E_ASSURANCE_REPORT.md` | Assurance evidence |
| `DIIAC_ARCHITECTURE_AND_CAPABILITIES_PICTURE.md` | Architecture overview |
| `DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md` | Technical architecture |
| `LOCAL_AUTH_TESTING.md` | Dev/test utility |
| `SECURITY.md` | Security policy |
| `RELEASE_NOTES_V1_2_0.md` | Release information |
| `README.md` | Needs URL update (see §7 above) |
| `GOVERNANCE_EXTENSIONS_V1_SPEC.md` | Extensions spec |
| `CHANGELOG.md` | Version history |

### Exclude from customer release (internal Vendorlogic only)

| File | Reason |
|------|--------|
| `HANDOFF.md` | Internal dev handoff notes |
| `PRODUCT_ROADMAP_V1_3_0.md` | Internal roadmap — not for customer release |
| `BASELINE_STATUS_AND_FUTURE_ENHANCEMENTS.md` | Internal status tracking |
| `RELEASE_LOCK_V1_2_0.md` | Internal dev artifact |
| `CUSTOMER_FORK_MODEL.md` | Internal model description |
| `DIIAC_V1_2_0_COMPREHENSIVE_BRIEFING.md` | Internal briefing |
| `DIIAC_V1_2_0_DEBUG_AND_TEST_REPORT.md` | Internal debug report |
| `DIIAC_ARCHITECTURE_ALIGNMENT_REPORT.md` | Internal alignment doc |
| `VENDORLOGIC_LOCAL_STAGING_GUIDE.md` | Vendorlogic-specific staging |
| `VENDORLOGIC_DEPLOYMENT_GUIDE.md` | Vendorlogic-specific deployment |
| `COPILOT_ENTRA_PRODUCTION_CHECKLIST.md` | Internal Copilot checklist |
| `CUSTOMER_RELEASE_AUDIT.md` | This file — internal only |

---

## What does NOT need to change

| Area | Why |
|------|-----|
| `app.py` (Governance Runtime) | Reads only from env vars — no customer-specific values |
| `backend-ui-bridge/` | No hardcoded customer values; configures from env |
| `docker-compose.yml` | Generic — no customer IDs |
| `docker-compose.staging.yml` | Generic |
| `tests/` | No customer-specific assertions |
| `contracts/` | Generic schema |
| `monitoring/` | Generic dashboards |
| `requirements.txt` / `pyproject.toml` | Generic |
| `.gitignore` | Generic |
| `deploy/kubernetes/*.yaml` | Image refs are correct; env var placeholders already in place |

---

## Multi-customer delivery process

When onboarding a new customer:

1. Customer clones `DIIaC-V1.2.0c-Production-Customer-Release`
2. Customer copies `customer-config/_template/` → `customer-config/<their-id>/`
3. Customer fills in their Azure tenant, Entra app IDs, group OIDs
4. (Phase B) Customer populates Azure Key Vault with secrets
5. Customer runs `DIIAC_CUSTOMER_ID=<their-id> bash scripts/pull-keyvault-secrets.sh`
6. Customer runs `docker compose up`

No code changes needed — everything is driven by `customer-config/<their-id>/config.env`.

---

## Customer release tag / locking

The customer release repo should:
- Have a `v1.2.0` git tag on its main branch
- Have branch protection on `main` (no direct pushes; PR + review required)
- Be updated only when Vendorlogic cuts a new platform release

When Vendorlogic releases v1.3.0:
- Create `DIIaC-V1.3.0c-Production-Customer-Release` (separate repo)
- Existing customers on v1.2.0 are not affected unless they opt in to upgrade

---

## How to apply these changes

Run the automated script from within the `DIIaC-V1.2.0c-Production-Customer-Release` repo:

```bash
bash scripts/prepare-customer-release.sh
```

This script performs all transformations above and reports any remaining manual steps.
See `scripts/prepare-customer-release.sh` for full detail.
