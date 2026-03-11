# Entra ID Setup Guide for DIIaC (vendorlogic.io)

> This document defines the **required account/app configuration** for DIIaC bridge integration with Microsoft Entra ID.
> It does not create credentials automatically.

## Tenant Details

- Domain: `vendorlogic.io`
- Tenant ID: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`

---

## 1) App Registration (Required)

Create an Entra app registration:

- Display name: `diiac-bridge-gateway`
- Supported account type: single tenant (`vendorlogic.io`)
- Redirect URI (for interactive test client): `http://localhost:3001/auth/callback`

Record:
- `Application (client) ID` → use as `ENTRA_EXPECTED_AUDIENCE`
- `Directory (tenant) ID` should match: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`

### App Roles Configuration

In the app registration manifest, define two app roles:

```json
"appRoles": [
  {
    "allowedMemberTypes": ["User", "Application"],
    "displayName": "DIIaC Admin",
    "description": "Full admin access to DIIaC governance bridge",
    "isEnabled": true,
    "value": "admin"
  },
  {
    "allowedMemberTypes": ["User", "Application"],
    "displayName": "DIIaC Customer",
    "description": "Customer access to DIIaC governed operations",
    "isEnabled": true,
    "value": "customer"
  }
]
```

## 2) Service Account (Recommended for Non-Interactive Tests)

Create one test service account in Entra:

- UPN: `svc-diiac-copilot@vendorlogic.io`
- Display name: `DIIaC Copilot Service Account`
- Enforce MFA according to policy (or conditional bypass only in isolated test environment)
- Assign least privilege app/Graph permissions required for pilot scope

## 3) Role Mapping Strategy

DIIaC bridge expects governance roles: `admin` and `customer`.

### Option A: App Roles (Preferred)

Assign the `admin` or `customer` app roles to users/groups in Entra. These appear in the `roles` claim of the JWT.

### Option B: Group Membership Mapping

Map Entra group Object IDs to DIIaC roles via `ENTRA_GROUP_TO_ROLE_JSON`:

```json
{
  "4ef7c128-a3f2-4c7d-a51d-c893e5944c88": "admin",
  "c1ffce74-ccd6-49f5-810f-1754e11da6c5": "customer"
}
```

### Option C: Principal Mapping (client_credentials)

For app-only tokens that do not include `groups`/`roles`, map `appid`/`azp` via `ENTRA_PRINCIPAL_TO_ROLE_JSON`:

```json
{
  "b726558d-f1c6-48f7-8a3d-72d5db818d0f": "admin"
}
```

**Resolution priority:** App roles → Group membership → Principal mapping.

## 4) Bridge Environment Configuration

Set these env vars in `backend-ui-bridge/.env` (or root `.env` with compose):

```bash
# Production mode (recommended)
AUTH_MODE=entra_jwt_rs256
ENTRA_ROLE_CLAIM=roles
ENTRA_GROUP_TO_ROLE_JSON={"4ef7c128-a3f2-4c7d-a51d-c893e5944c88":"admin","c1ffce74-ccd6-49f5-810f-1754e11da6c5":"customer"}

# Optional app/service-principal fallback for client_credentials tokens without groups/roles
ENTRA_PRINCIPAL_TO_ROLE_JSON={"b726558d-f1c6-48f7-8a3d-72d5db818d0f":"admin"}

ENTRA_EXPECTED_TENANT_ID=1384b1c5-2bae-45a1-a4b4-e94e3315eb41
ENTRA_EXPECTED_AUDIENCE=b726558d-f1c6-48f7-8a3d-72d5db818d0f
ENTRA_EXPECTED_ISSUERS=https://login.microsoftonline.com/1384b1c5-2bae-45a1-a4b4-e94e3315eb41/v2.0,https://sts.windows.net/1384b1c5-2bae-45a1-a4b4-e94e3315eb41/

# Optional override (if private cloud/proxy requires custom discovery endpoint)
ENTRA_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/1384b1c5-2bae-45a1-a4b4-e94e3315eb41/v2.0/.well-known/openid-configuration
```

### Integration-Test Fallback (Not Production)

```bash
AUTH_MODE=entra_jwt_hs256
ENTRA_JWT_HS256_SECRET=<integration-test-shared-secret>
ENTRA_EXPECTED_TENANT_ID=1384b1c5-2bae-45a1-a4b4-e94e3315eb41
ENTRA_EXPECTED_AUDIENCE=b726558d-f1c6-48f7-8a3d-72d5db818d0f
```

## 5) API Endpoints

### Authentication Status

```bash
GET /auth/status
```

Returns current auth mode and Entra configuration (no auth required).

### Copilot Governance Intercept

```bash
# Intercept a Copilot request (admin or customer)
POST /api/intercept/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "prompt": "What SD-WAN vendor should we select?",
  "source": "copilot",
  "context": { "workspace": "uk-rail-network" }
}

# Record a Copilot response for governance audit
POST /api/intercept/response
Authorization: Bearer <token>
Content-Type: application/json

{
  "intercept_id": "<id from intercept/request>",
  "response_text": "Based on the analysis...",
  "model": "gpt-4o",
  "confidence": 0.85
}

# Human approval gate for Copilot responses (admin only)
POST /api/intercept/approval
Authorization: Bearer <token>
Content-Type: application/json

{
  "intercept_id": "<id>",
  "decision": "approve",
  "justification": "Reviewed and confirmed against governance criteria"
}
```

All intercept events are recorded in the hash-chained trust ledger with actor lineage.

## 6) Minimum Operational Checks

1. Acquire bearer token for test principal
2. Call bridge endpoint with Authorization header:
   ```bash
   curl -X POST http://localhost:3001/api/intercept/request \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"prompt":"test governance intercept","source":"copilot"}'
   ```
3. Confirm response includes `actor` lineage and `ledger_hash`
4. Validate rejected tokens for:
   - Wrong tenant (`tid` mismatch) → `401 token_invalid`
   - Wrong audience (`aud` mismatch) → `401 claim_validation_failed`
   - Expired token → `401 token_expired`
   - No role resolved → `403 no_diiac_role`

## 7) Security and Governance Controls

- Restrict service account permissions to pilot scope only
- Rotate JWT secret for non-production integration mode regularly
- Prefer certificate-based auth and managed identities for production deployment
- Ensure all intercept/response/approval events are exported in audit chain
- `AUTH_MODE=entra_jwt_rs256` validates via live Entra OIDC/JWKS — no shared secrets
- `AUTH_MODE=entra_jwt_hs256` is only for isolated integration tests with minted tokens

## 8) Backward Compatibility

When `AUTH_MODE` is unset or not `entra_jwt_*`:
- The Entra middleware is a no-op pass-through
- Legacy `x-role` header authentication continues to work
- All existing API calls remain functional without any changes
- The frontend falls back to legacy header auth when no access token is set
