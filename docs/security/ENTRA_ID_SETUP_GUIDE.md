# Entra ID Setup Guide (v1.3.0-ui)

This guide aligns Entra configuration with the current Vendorlogic UI deployment.

## Current IDs

- Tenant ID: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- App ID (API/UI in current build): `b726558d-f1c6-48f7-8a3d-72d5db818d0f`
- Admin group ID: `81786818-de16-4115-b061-92fce74b00bd`
- Standard group ID: `9c7dd0d4-5b44-4811-b167-e52df21092d8`

## Required Redirect URIs

Add and keep these redirect URIs in the SPA app registration:

- `https://diiacui.vendorlogic.io/auth/callback`
- Local dev URI as needed (for example `http://localhost:5174/auth/callback`)

A missing custom-domain callback causes `AADSTS50011` redirect mismatch.

## Bridge Validation Settings

Set these bridge env values:

- `AUTH_MODE=entra_jwt_rs256`
- `ENTRA_EXPECTED_TENANT_ID=<tenant-guid>`
- `ENTRA_EXPECTED_AUDIENCE=api://<app-id-guid>`
- `ENTRA_EXPECTED_ISSUERS=<issuer-list>`
- `ENTRA_GROUP_TO_ROLE_JSON=<group->role-json>`
- `ENTRA_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant>/v2.0/.well-known/openid-configuration`
- `ENTRA_JWKS_URI=https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys`

## Frontend Settings

Build-time vars:

- `VITE_ENTRA_CLIENT_ID`
- `VITE_ENTRA_TENANT_ID`
- `VITE_ENTRA_REDIRECT_URI`
- `VITE_ENTRA_GROUP_MAP`

For production, redirect URI must be the custom domain callback URL.

## Role Mapping

Use group mapping JSON:

```json
{"81786818-de16-4115-b061-92fce74b00bd":{"role":"admin"},"9c7dd0d4-5b44-4811-b167-e52df21092d8":{"role":"standard"}}
```

## Verification

1. Sign in as admin user and confirm admin features are available.
2. Sign in as standard user and confirm restricted behavior.
3. Confirm bridge `/auth/status` reports Entra mode enabled.
