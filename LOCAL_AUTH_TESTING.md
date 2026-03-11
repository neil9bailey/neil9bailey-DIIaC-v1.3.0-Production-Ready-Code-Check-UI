# Local Entra ID Authentication Testing

Two-phase guide: HS256 (no Azure needed) then RS256 (real Entra tenant).

---

## Option 1 — HS256 (local-only, no Azure required)

### 1. Create root `.env`

Create `.env` in the repo root (next to `docker-compose.yml`):

```env
# Host ports
RUNTIME_HOST_PORT=8000
BRIDGE_HOST_PORT=3001
FRONTEND_HOST_PORT=5173

# Bridge LLM (leave OPENAI_API_KEY blank if not needed)
LLM_INGESTION_ENABLED=true
LLM_STUB_ENABLED=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# ── Entra HS256 test mode ─────────────────────────────────────────
AUTH_MODE=entra_jwt_hs256
ENTRA_JWT_HS256_SECRET=diiac-local-test-secret-change-me-in-prod!!
ENTRA_ROLE_CLAIM=roles
ENTRA_EXPECTED_TENANT_ID=local-test-tenant
ENTRA_EXPECTED_AUDIENCE=diiac-bridge-local
ENTRA_EXPECTED_ISSUERS=https://diiac-local-test-issuer
```

### 2. Restart the stack

```powershell
docker compose down
docker compose up -d
docker compose logs backend-ui-bridge | Select-String "\[entra\]"
```

You should see:
```
[entra] AUTH_MODE=entra_jwt_hs256
[entra] tenant=local-test-tenant
[entra] audience=diiac-bridge-local
```

### 3. Verify auth is active

```powershell
curl http://localhost:3001/auth/status
```

Expected:
```json
{
  "auth_mode": "entra_jwt_hs256",
  "entra_enabled": true,
  "tenant_id": "local-test-tenant",
  "audience": "diiac-bridge-local"
}
```

### 4. Generate test tokens

Install `jose` locally (one-time), then run the helper script:

```powershell
npm install jose           # one-time, in the repo root
node scripts/generate-test-token.mjs              # admin token, 1 h
node scripts/generate-test-token.mjs customer      # customer token
node scripts/generate-test-token.mjs --expired     # expired token (negative test)
```

The script prints the JWT and ready-to-paste curl commands.

### 5. Test the auth flow

```powershell
# Save token to a variable (PowerShell)
$TOKEN = (node scripts/generate-test-token.mjs 2>$null | Select-String "^ey").ToString().Trim()

# 5a. No token → 401
curl http://localhost:3001/api/intercept/request -X POST -H "Content-Type: application/json" -d '{"prompt":"test"}'

# 5b. Valid admin token → 200
curl -H "Authorization: Bearer $TOKEN" -X POST -H "Content-Type: application/json" -d '{"prompt":"test"}' http://localhost:3001/api/intercept/request

# 5c. Expired token → 401 token_expired
$EXPIRED = (node scripts/generate-test-token.mjs --expired 2>$null | Select-String "^ey").ToString().Trim()
curl -H "Authorization: Bearer $EXPIRED" http://localhost:3001/auth/status
```

### 6. What to verify

| Test | Expected |
|---|---|
| No `Authorization` header | `401` — `authentication_required` |
| Valid admin token | `200` — request passes through |
| Valid customer token | `200` on customer-allowed endpoints |
| Expired token | `401` — `token_expired` |
| Garbage token | `401` — `token_invalid` |
| Valid token with no `roles` claim | `403` — `no_diiac_role` |

---

## Option 2 — RS256 (real Entra tenant)

### Prerequisites

- Azure AD / Entra ID tenant (e.g. `vendorlogic.io`)
- Permission to create App Registrations

### 1. Create App Registration in Azure Portal

1. Go to **Azure Portal → Entra ID → App registrations → New registration**
2. Name: `diiac-bridge-gateway`
3. Supported account types: **Single tenant**
4. Redirect URI: `http://localhost:3001/auth/callback` (Web)
5. Note the **Application (client) ID** — this is your `ENTRA_EXPECTED_AUDIENCE`
6. Note the **Directory (tenant) ID** — this is your `ENTRA_EXPECTED_TENANT_ID`

### 2. Add App Roles

In the App Registration → **App roles → Create app role**:

| Display name | Value | Allowed member types |
|---|---|---|
| DIIaC Admin | `admin` | Users/Groups + Applications |
| DIIaC Customer | `customer` | Users/Groups + Applications |

### 3. Assign users to roles

**Entra ID → Enterprise applications → `diiac-bridge-gateway` → Users and groups → Add user/group**, then assign the `admin` or `customer` role.

### 4. Update root `.env`

```env
AUTH_MODE=entra_jwt_rs256
ENTRA_ROLE_CLAIM=roles
ENTRA_EXPECTED_TENANT_ID=<your-tenant-id>
ENTRA_EXPECTED_AUDIENCE=<your-app-client-id>
ENTRA_EXPECTED_ISSUERS=https://login.microsoftonline.com/<your-tenant-id>/v2.0,https://sts.windows.net/<your-tenant-id>/
# Optional group-to-role mapping:
# ENTRA_GROUP_TO_ROLE_JSON={"<group-object-id>":"admin","<group-object-id>":"customer"}
```

### 5. Restart and test

```powershell
docker compose down
docker compose up -d
```

### 6. Obtain a token

**Option A — Client credentials (app-only, for automation/testing):**

```powershell
# Create a client secret in Azure Portal → App Registration → Certificates & secrets
curl -X POST "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token" `
  -d "client_id=<app-client-id>" `
  -d "client_secret=<your-client-secret>" `
  -d "scope=<app-client-id>/.default" `
  -d "grant_type=client_credentials"
```

Add a principal mapping so the app-only token gets a role:
```env
ENTRA_PRINCIPAL_TO_ROLE_JSON={"<app-client-id>":"admin"}
```

**Option B — Delegated (user login via browser):**

Use MSAL or Postman's OAuth 2.0 authorization code flow against:
- Authorize: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize`
- Token: `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token`
- Scope: `api://<app-client-id>/access_as_user` (or `.default`)

### 7. Test with the real token

```powershell
$TOKEN = "<paste-access-token-here>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:3001/auth/status
curl -H "Authorization: Bearer $TOKEN" -X POST -H "Content-Type: application/json" -d '{"prompt":"test"}' http://localhost:3001/api/intercept/request
```

---

## Switching back to legacy mode

Remove or comment out `AUTH_MODE` in `.env` and restart:

```powershell
# AUTH_MODE=
docker compose down && docker compose up -d
```

The middleware becomes a no-op and the old `x-role` header auth works as before.
