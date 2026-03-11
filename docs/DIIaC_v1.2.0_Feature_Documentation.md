# DIIaC v1.2.0 — Platform Capabilities & Feature Documentation

**Decision Intelligence Infrastructure as Code**
Version 1.2.0 | Production-Ready Release | March 2026

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Architecture](#2-architecture)
3. [Microsoft Entra ID Integration](#3-microsoft-entra-id-integration)
4. [Role-Based Access Control (RBAC)](#4-role-based-access-control-rbac)
5. [Governance Decision Engine](#5-governance-decision-engine)
6. [LLM Integration & AI Governance](#6-llm-integration--ai-governance)
7. [GitHub Copilot Governance Intercept](#7-github-copilot-governance-intercept)
8. [Cryptographic Signing & Trust Ledger](#8-cryptographic-signing--trust-ledger)
9. [Operational Dashboard](#9-operational-dashboard)
10. [Admin Console](#10-admin-console)
11. [Multi-Role Governed Compile](#11-multi-role-governed-compile)
12. [Policy Impact Analysis](#12-policy-impact-analysis)
13. [Audit & Compliance](#13-audit--compliance)
14. [Configuration Management](#14-configuration-management)
15. [Deployment](#15-deployment)
16. [Future Roadmap](#16-future-roadmap)

---

## 1. Platform Overview

DIIaC is an enterprise governance platform that brings **Infrastructure as Code principles to decision-making**. Every AI-assisted output, strategic decision, and governance action is:

- **Deterministically governed** — policy levels (P0–P5) and reasoning levels (R0–R5) enforce what must be present
- **Cryptographically signed** — Ed25519 signatures on every decision pack
- **Immutably recorded** — chained-hash ledger (JSONL) creates an audit trail
- **Identity-bound** — every action is attributed to an Entra ID user with role context

The platform governs two primary workflows:
1. **Strategic Decision Governance** — human intent → AI-assisted analysis → policy-bound output → signed artefacts
2. **Copilot Governance Intercept** — intercepts GitHub Copilot prompts/responses, applies governance policy, and records an approval chain

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend (Vite)                  │
│         MSAL Auth → Entra ID OIDC (PKCE)               │
│         Role-based UI rendering (Admin/Standard)         │
├─────────────────────────────────────────────────────────┤
│              Node.js Bridge (Express :3001)              │
│    Entra JWT validation │ RBAC │ LLM orchestration      │
│    Ed25519 signing │ Ledger │ Copilot intercept          │
├─────────────────────────────────────────────────────────┤
│         Python Governance Runtime (Flask :8000)          │
│   Merkle trees │ Deterministic compile │ Scoring         │
│   Business profiles │ Audit export │ DB management       │
├─────────────────────────────────────────────────────────┤
│                     Data Layer                           │
│   /workspace/ledger/ledger.jsonl   (immutable ledger)   │
│   /workspace/artefacts/            (decision packs)     │
│   /workspace/contracts/            (schemas, keys)      │
│   /workspace/state/diiac.sqlite3   (operational DB)     │
└─────────────────────────────────────────────────────────┘
```

### Three-Tier Service Architecture

| Service | Technology | Port | Purpose |
|---------|-----------|------|---------|
| **Frontend** | React 19 + Vite 7 + TypeScript | 5173 | MSAL auth, role-based UI, governance workflows |
| **Backend Bridge** | Node.js + Express (ESM) | 3001 | JWT validation, RBAC, LLM calls, signing, ledger, Copilot intercept |
| **Governance Runtime** | Python 3.11 + Flask | 8000 | Deterministic governance, Merkle trees, scoring, compile, audit |

---

## 3. Microsoft Entra ID Integration

### Authentication Flow (NEW in v1.2.0)

DIIaC now uses **MSAL Authorization Code Flow with PKCE** — the industry-standard SPA authentication pattern. No more token pasting.

```
User visits DIIaC → "Sign in with Entra ID" button
    → Browser redirects to login.microsoftonline.com
    → User authenticates with @vendorlogic.io credentials
    → Entra redirects back to /auth/callback with auth code
    → MSAL.js exchanges code for tokens (PKCE — no client secret exposed)
    → ID token contains group OIDs → role resolved → UI renders
    → Access token attached to all API calls as Bearer token
    → Token auto-refreshes every 4 minutes (silent acquisition)
```

### Entra App Registration

| Setting | Value |
|---------|-------|
| **App Name** | diiac-bridge-gateway |
| **Client ID** | `b726558d-f1c6-48f7-8a3d-72d5db818d0f` |
| **Tenant ID** | `1384b1c5-2bae-45a1-a4b4-e94e3315eb41` |
| **Domain** | vendorlogic.io |
| **Account Type** | Single tenant (My organization only) |
| **App ID URI** | `api://b726558d-f1c6-48f7-8a3d-72d5db818d0f` |
| **SPA Redirect** | `http://localhost:5173/auth/callback` |
| **API Scope** | `access_as_user` — delegated, user-consent |
| **Group Claims** | SecurityGroup with `emit_as_roles` |

### Token Configuration

- **groupMembershipClaims**: `SecurityGroup` — security group OIDs emitted in tokens
- **Optional Claims**: `groups` configured on ID token, access token, and SAML with `emit_as_roles`
- Group OIDs appear in the `roles` claim — both frontend and backend handle this correctly

### Backend JWT Validation

The Node.js bridge validates tokens via two modes:

| Mode | Env Var | Use Case |
|------|---------|----------|
| `entra_jwt_rs256` | `AUTH_MODE=entra_jwt_rs256` | **Production** — validates RS256 JWTs against Entra JWKS endpoint |
| `entra_jwt_hs256` | `AUTH_MODE=entra_jwt_hs256` | **Integration testing** — validates HS256 with shared secret |
| Legacy | AUTH_MODE unset | **Dev mode** — x-role header auth, no token required |

Validation checks: signature, audience, issuer, tenant ID, expiry.

---

## 4. Role-Based Access Control (RBAC)

### Entra Security Groups

| Entra Group | Object ID | DIIaC Role | Access Level |
|-------------|-----------|------------|-------------|
| **Admins** | `81786818-de16-4115-b061-92fce74b00bd` | `admin` | Full platform access |
| **Standard Users** | `9c7dd0d4-5b44-4811-b167-e52df21092d8` | `standard` | Core governance UI |
| *Customer* | *Deferred to SaaS phase* | *customer* | *Tenanted context-aware* |

### Role Resolution Priority

The system resolves roles in this order (highest priority first):

1. **App roles** in `roles` claim (named values like `"admin"`, `"StandardUser"`)
2. **Group OIDs** in `roles` claim (matched against `ENTRA_GROUP_TO_ROLE_JSON` — handles `emit_as_roles`)
3. **Group OIDs** in `groups` claim (standard group membership — handles non-emit_as_roles)
4. **Principal ID** mapping (for client_credentials / service principal tokens)

Role priority: `admin` (4) > `standard` (3) > `customer` (2) > `viewer` (1)

Role name normalisation handles common variations: `"Admins"` → `admin`, `"Standard Users"` → `standard`, `"StandardUser"` → `standard`.

### Sub-Role Framework (Future-Ready)

The group mapping supports sub-roles for future C-suite functionality:

```json
{
  "<cto-group-oid>":  {"subrole": "cto"},
  "<ciso-group-oid>": {"subrole": "ciso"},
  "<architect-oid>":  {"subrole": "architect"}
}
```

Sub-roles are carried through the full stack (frontend identity, backend `req.entraAuth.subroles`, actor lineage) but do not yet gate UI functionality. Ready for phase 2.

### UI Access Matrix

| Feature | Admin | Standard | Description |
|---------|:-----:|:--------:|-------------|
| Entra ID Sign-in | Y | Y | MSAL challenge auth |
| Governance Notice | Y | Y | AI untrusted-input disclaimer |
| Human Input Panel | - | Y | Strategic intent submission |
| Exploratory Decision Draft | Y (full controls) | Y (defaults only) | AI-assisted governance execution |
| Report Viewer & Export | Y | Y | View/download governed reports |
| Policy Impact Analysis | Y | - | P0–P5 severity assessment |
| Trust Dashboard | Y | - | Ledger integrity verification |
| Multi-Role Governed Compile | Y | - | C-suite multi-stakeholder workflow |
| Admin Console | Y | - | Health, metrics, logs, DB, exports |
| Operational Dashboard | Y | - | Integrations, trends, config, approvals |
| User Name in Header | Y | Y | Shows authenticated identity |
| Role Badge | Y | Y | Shows resolved role + sub-roles |

### Endpoint Access Matrix

| Endpoint Category | Admin | Standard | Description |
|-------------------|:-----:|:--------:|-------------|
| `/auth/status`, `/auth/callback` | Public | Public | Auth configuration |
| `/auth/me` | Y | Y | Returns identity + role + sub-roles |
| `/api/human-input` | Y | Y | Store human intent |
| `/govern/decision` | Y | - | Execute governance contract |
| `/trust`, `/trust/status` | Y | Y | Ledger state |
| `/verify/*` | Y | Y | Signature/pack/merkle verification |
| `/executions/*/reports` | Y | Y | Report listing & download |
| `/api/business-profiles` | Y | Y | Available business profiles |
| `/api/intercept/*` | Y | Y | Copilot governance intercept |
| `/api/llm-governed-compile` | Y | - | Hybrid LLM + deterministic compile |
| `/admin/*` | Y | - | All admin endpoints |

---

## 5. Governance Decision Engine

### Execution Flow

```
Human Input → AI Generation → Section Enforcement → Signing → Hashing → Manifest → Ledger
```

1. **Human Input Capture** — user submits strategic intent as JSON (stored in `/workspace/artefacts/human-input/`)
2. **AI Generation** — OpenAI generates analysis based on reasoning level (R0–R5) and policy level (P0–P5)
3. **Section Enforcement** — required sections are injected if AI omits them (marked `enforced: true`)
4. **Decision Summary** — creates `decision_summary.json` classified as `BOARD_READY` under `DIIaC_CORE_V1` governance contract
5. **Cryptographic Signing** — Ed25519 signature over execution context, written as `.sig` + `.sigmeta.json`
6. **Deterministic Hashing** — all artefacts hashed (SHA256), concatenated alphabetically, hashed again → `pack_hash`
7. **Governance Manifest** — `governance_manifest.json` records every artefact hash, execution metadata
8. **Ledger Append** — `GOVERNED_EXECUTION` entry chained to ledger with previous_hash linkage

### Reasoning Levels (R0–R5)

| Level | Name | Sections Generated |
|-------|------|-------------------|
| R0 | Executive Only | executive_summary |
| R1 | Structured | executive_summary |
| R2 | Analytical | executive_summary, strategic_context |
| R3 | Strategic | executive_summary, strategic_context, market_analysis |
| R4 | Scenario | + risk_matrix |
| R5 | Adversarial Deep | + financial_model, scenario_analysis, implementation_roadmap, governance_implications, vendor_scoring, board_recommendation |

### Policy Levels (P0–P5)

| Level | Name | Additional Requirements | Severity |
|-------|------|------------------------|----------|
| P0 | Minimal | (none) | LOW |
| P1 | Standard | (none) | LOW |
| P2 | Enhanced | risk_matrix | MEDIUM |
| P3 | Regulated | regulatory_position | MEDIUM |
| P4 | High Assurance | audit_trail | HIGH |
| P5 | Critical Infrastructure | trace_manifest | CRITICAL |

---

## 6. LLM Integration & AI Governance

### LLM Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_INGESTION_ENABLED` | `false` | Enable/disable LLM calls |
| `LLM_STUB_ENABLED` | `false` | Deterministic fallback when no API key |
| `OPENAI_API_KEY` | (none) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use |

### AI Governance Principle

**All AI-assisted content is treated as untrusted input.** The governance notice displayed at the top of the UI states:

> *AI-assisted content is treated as untrusted input. All outputs are deterministically governed, policy-bound, and recorded in an immutable audit ledger.*

This means:
- AI output is **never trusted directly** — it passes through section enforcement
- Missing required sections are **deterministically injected** with `enforced: true`
- Every execution is **signed and hashed** regardless of AI output quality
- The **ledger records what happened**, not what the AI said

### Stub Mode

When `LLM_STUB_ENABLED=true` and no API key is available, the system generates deterministic stub output. This enables:
- Local development without API costs
- Offline testing of the full governance pipeline
- CI/CD validation of signing, hashing, and ledger integrity

---

## 7. GitHub Copilot Governance Intercept

DIIaC provides a governance layer for GitHub Copilot interactions, creating an auditable chain of custody for AI-assisted code.

### Intercept Workflow

```
Copilot Prompt → Request Intercept → Response Recording → Approval Decision
     │                  │                    │                    │
     │            prompt_hash          response_hash         decision
     │            ledger entry         ledger entry         ledger entry
     │           (COPILOT_INTERCEPT)  (COPILOT_RESPONSE)  (COPILOT_APPROVAL)
```

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/intercept/request` | POST | Intercepts Copilot prompt — hashes prompt, records to ledger, returns intercept_id |
| `/api/intercept/response` | POST | Records Copilot response — hashes response, records model + confidence to ledger |
| `/api/intercept/approval` | POST | Admin decision — approve/reject/escalate with justification, recorded to ledger |

### Approval Queue

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/intercept/approval/pending` | GET | Lists all pending approval items |
| `/api/intercept/approval/submit` | POST | Submits an approval request (with risk level) |
| `/api/intercept/approval/decide` | POST | Makes approval decision (APPROVED/REJECTED/ESCALATED) |

### What This Means

Every Copilot interaction in your organisation can be:
- **Intercepted** before execution with a SHA256 prompt hash
- **Recorded** with model and confidence metadata
- **Approved/rejected** by admin with justification
- **Audited** via the immutable ledger — who asked what, what was generated, who approved it

---

## 8. Cryptographic Signing & Trust Ledger

### Ed25519 Signing

Every governance decision pack is cryptographically signed:

- **Algorithm**: Ed25519 (elliptic curve, 128-bit security)
- **Key Modes**: `configured` (PEM from env) or `ephemeral` (generated at startup)
- **Artefacts**: `signed_export.sig` (raw signature) + `signed_export.sigmeta.json` (metadata)
- **Payload**: execution_id + context_hash + signing_key_id + timestamp
- **Verification**: `POST /verify/pack` validates signature, hash, and manifest consistency

### Immutable Ledger

`/workspace/ledger/ledger.jsonl` — a JSON Lines file where every entry is chained:

```
Record N:
  previous_hash = SHA256(Record N-1)
  record_hash = SHA256(this record including previous_hash)
```

#### Ledger Entry Types

| Type | Triggered By | What's Recorded |
|------|-------------|-----------------|
| `GOVERNED_EXECUTION` | `/govern/decision` | execution_id, provider, R/P levels, context_hash, pack_hash, artefact_count |
| `COPILOT_INTERCEPT` | `/api/intercept/request` | intercept_id, source, actor, prompt_hash |
| `COPILOT_RESPONSE` | `/api/intercept/response` | intercept_id, actor, response_hash, model, confidence |
| `COPILOT_APPROVAL` | `/api/intercept/approval` | intercept_id, decision, justification, approver |
| `CONFIG_CHANGE_REQUEST` | `/admin/config/change-request` | request_id, field, actor |
| `CONFIG_CHANGE_DECISION` | Config decision endpoint | request_id, decision, actor |
| `APPROVAL_QUEUE_SUBMIT` | `/api/intercept/approval/submit` | approval_id, intercept_id, actor |
| `APPROVAL_QUEUE_DECISION` | `/api/intercept/approval/decide` | approval_id, decision, actor |

### Trust Dashboard

The UI's Trust Dashboard (`/trust`) displays:
- Ledger validity (chain integrity)
- Total record count
- Current ledger root hash
- Frozen state flag

### Merkle Tree Verification

The Python governance runtime provides Merkle tree construction for artefact verification:
- Build Merkle tree from artefact hashes
- Generate inclusion proofs for individual artefacts
- Verify proofs independently

---

## 9. Operational Dashboard

**Admin-only overlay** — opened via the gear icon in the header.

### Sections

| Section | Data Source | What It Shows |
|---------|-----------|---------------|
| **Global Status** | `/admin/integrations/health` | PASS/WARN/FAIL with critical alerts count |
| **Entra Identity** | Health endpoint | Auth mode, tenant, audience, role map status, issuer pinning |
| **LLM Integration** | Health endpoint | API key status, model, stub mode, ingestion enabled |
| **Approval Ops** | Health endpoint | Pending count, persistence, decision SLA |
| **Runtime** | Health endpoint | Python status, trust ledger, DB integrity, replay verifier |
| **Trend Summary** | `/admin/integrations/summary/trends` | 24h intercept stats — allow/restrict/require-approval percentages, top block reasons |
| **Effective Config** | `/admin/config/effective` | Current auth, signing, LLM, TLS, offload, Python runtime settings |
| **Pending Approvals** | `/api/intercept/approval/pending` | Approval queue with risk levels |
| **Config Changes** | `/admin/config/change-history` | Change request history with statuses |
| **Change Request Form** | `/admin/config/change-request` | Submit governed config changes |

---

## 10. Admin Console

**Admin-only panel** — four tabs.

### Tabs

| Tab | Features |
|-----|----------|
| **Overview** | Service health, metrics snapshot, service status, container status, execution verification |
| **Exports** | Audit export generation, export history, download links |
| **Logs** | Backend logs, ledger logs, execution-specific logs |
| **DB** | Database status (path, size, mtime), table inspection, compaction |

---

## 11. Multi-Role Governed Compile

**Admin-only panel** — combines LLM synthesis with deterministic governance compile.

### Workflow

1. Select **business profile** (loaded from contracts or Python runtime)
2. Choose **governance schema** (e.g., `GENERAL_SOLUTION_BOARD_REPORT_V1`)
3. Select **C-suite role** (CIO, CTO, CFO, CISO, etc.)
4. Set **governance modes**, **reasoning level** (R0–R5), **policy level** (P0–P5)
5. Define **assertions**, **non-negotiables**, **risk flags**
6. Optionally provide **human intent** for LLM context
7. Submit → system generates LLM output + deterministic compile + role evidence

### Output

- LLM output hash (SHA256)
- Role input evidence stored
- Deterministic compile via Python runtime
- Execution ID for downstream verification

---

## 12. Policy Impact Analysis

**Admin-only panel** — analyses the impact of governance policy level changes.

| Policy Level | Severity | Impacted Controls | Findings |
|-------------|----------|-------------------|----------|
| P0 | LOW | 0 | 0 |
| P1 | LOW | 2 | 1 |
| P2 | MEDIUM | 4 | 2 |
| P3 | MEDIUM | 6 | 3 |
| P4 | HIGH | 8 | 5 |
| P5 | CRITICAL | 12 | 8 |

---

## 13. Audit & Compliance

### Audit Export

Admin users can generate audit export packages containing:
- Execution artefacts
- Ledger entries
- Signed manifests
- Governance metadata

Exports are generated via the Python runtime and downloadable as archives.

### Actor Lineage

Every API action records an actor lineage:

```json
{
  "subject": "entra-user-oid",
  "name": "Neil Bailey",
  "email": "nbailey@vendorlogic.io",
  "role": "admin",
  "subroles": [],
  "tenant_id": "1384b1c5-2bae-45a1-a4b4-e94e3315eb41",
  "token_type": "delegated",
  "principal_id": null
}
```

This is attached to every ledger entry, providing full attribution for compliance audits.

---

## 14. Configuration Management

### Governed Config Changes

Configuration changes are themselves governed:

1. Admin submits change request (field, proposed value, reason)
2. Request is recorded in ledger as `CONFIG_CHANGE_REQUEST`
3. Another admin approves/rejects with justification
4. Decision recorded in ledger as `CONFIG_CHANGE_DECISION`

### Environment Variables

#### Frontend

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | Backend bridge URL (default: `http://localhost:3001`) |
| `VITE_ENTRA_CLIENT_ID` | Entra app registration client ID |
| `VITE_ENTRA_TENANT_ID` | Entra tenant ID |
| `VITE_ENTRA_REDIRECT_URI` | OIDC redirect URI (default: `{origin}/auth/callback`) |
| `VITE_ENTRA_GROUP_MAP` | JSON: group OID → role/subrole mapping |

#### Backend Bridge

| Variable | Description |
|----------|-------------|
| `AUTH_MODE` | `entra_jwt_rs256` (production), `entra_jwt_hs256` (test), or unset (legacy) |
| `ENTRA_EXPECTED_TENANT_ID` | Tenant ID for token validation |
| `ENTRA_EXPECTED_AUDIENCE` | Audience claim validation |
| `ENTRA_EXPECTED_ISSUERS` | Comma-separated issuer URLs for pinning |
| `ENTRA_GROUP_TO_ROLE_JSON` | Group OID → role mapping (flat or structured) |
| `ENTRA_PRINCIPAL_TO_ROLE_JSON` | Service principal → role mapping |
| `ENTRA_ROLE_CLAIM` | Claim name for roles (default: `roles`) |
| `SIGNING_ENABLED` | Enable Ed25519 signing (default: `true`) |
| `SIGNING_KEY_ID` | Signing key identifier |
| `SIGNING_PRIVATE_KEY_PEM` | Optional PEM-encoded private key |
| `LLM_INGESTION_ENABLED` | Enable LLM calls |
| `LLM_STUB_ENABLED` | Enable deterministic stub fallback |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model name (default: `gpt-4o-mini`) |
| `PYTHON_BASE_URL` | Governance runtime URL (default: `http://127.0.0.1:8000`) |

---

## 15. Deployment

### Docker Compose

Three services orchestrated via `docker-compose.yaml`:

```yaml
services:
  governance-runtime:    # Python 3.11 Flask (:8000)
  backend-ui-bridge:     # Node.js Express (:3001)
  frontend:              # React Vite (:5173)
```

All Entra ID environment variables are passed through from the host environment, enabling configuration without image rebuilds.

### Volumes

| Volume | Purpose |
|--------|---------|
| `diiac-artifacts` | Decision pack artefacts |
| `diiac-exports` | Generated exports |
| `diiac-audit-exports` | Audit export archives |
| `diiac-human-input` | Human intent submissions |

---

## 16. Future Roadmap

### Phase 2 — Sub-Role Functionality
- **CTO role** → CTO-specific panels and governance views
- **CISO role** → Security-focused assessment workflows
- **Architect role** → Architecture decision records

The sub-role framework is already wired through the stack — groups, tokens, identity context, and actor lineage all carry `subroles[]`. UI gating is the next step.

### Phase 3 — Customer Role (Tenanted SaaS)
- **Customer groups** with context: Transport, Finance, IT Service Provider, IT Enterprise Org
- Customer context pre-populates the Human Input Panel
- Tenant isolation for multi-organisation deployments
- Per-tenant business profile management

### Phase 4 — Extended Copilot Governance
- Real-time Copilot proxy integration
- Automated policy enforcement on prompts
- Risk scoring with ML-based classification
- Organisation-wide Copilot usage analytics

---

*This document reflects the state of DIIaC v1.2.0 as deployed against the vendorlogic.io Entra ID tenant.*
