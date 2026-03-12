# Local Auth Testing (v1.3.0-ui)

Use this guide for local/integration auth testing without changing production posture.

## Modes

- Development bypass: `AUTH_MODE` unset (legacy header role flow)
- Integration test mode: `AUTH_MODE=entra_jwt_hs256`
- Production mode: `AUTH_MODE=entra_jwt_rs256`

## HS256 Integration Test Setup

Set env variables for bridge:

- `AUTH_MODE=entra_jwt_hs256`
- `ENTRA_JWT_HS256_SECRET=<test-secret>`
- `ENTRA_EXPECTED_TENANT_ID=<tenant-guid>`
- `ENTRA_EXPECTED_AUDIENCE=api://<app-id-guid>`
- `ENTRA_EXPECTED_ISSUERS=<issuer>`
- `ENTRA_GROUP_TO_ROLE_JSON=<group-map-json>`

Generate a test token with script:

```powershell
node scripts/generate-test-token.mjs
```

Use token in API request:

```powershell
$token = "<jwt>"
curl -H "Authorization: Bearer $token" http://localhost:3101/auth/status
```

## Pass Criteria

- Token accepted with correct claims.
- Role resolved correctly from roles/groups mapping.
- Unauthorized or malformed tokens are rejected.

Do not use HS256 mode in production.
