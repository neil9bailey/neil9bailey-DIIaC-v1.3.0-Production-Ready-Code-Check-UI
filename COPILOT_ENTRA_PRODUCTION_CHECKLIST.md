# Copilot + Entra ID Production Checklist

> Execute this checklist after environment setup to verify end-to-end controls before production cutover.

## Pre-Flight

- [ ] Entra app registration `diiac-bridge-gateway` exists in tenant `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- [ ] App roles `admin` and `customer` defined in app manifest
- [ ] Service account `svc-diiac-copilot@vendorlogic.io` created and assigned appropriate role
- [ ] Group-to-role mappings configured in `ENTRA_GROUP_TO_ROLE_JSON` (if using group-based auth)
- [ ] Principal-to-role mappings configured in `ENTRA_PRINCIPAL_TO_ROLE_JSON` (if using client_credentials)

## Environment Configuration

- [ ] `AUTH_MODE=entra_jwt_rs256` set in bridge environment
- [ ] `ENTRA_EXPECTED_TENANT_ID` set to `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- [ ] `ENTRA_EXPECTED_AUDIENCE` set to the app registration client ID
- [ ] `ENTRA_EXPECTED_ISSUERS` includes both v2.0 and STS issuer URLs
- [ ] `ENTRA_JWT_HS256_SECRET` is **NOT** set in production environment
- [ ] Bridge `.env` file is not committed to git (verify `.gitignore`)

## Authentication Validation

- [ ] `GET /auth/status` returns `auth_mode: "entra_jwt_rs256"` and `entra_enabled: true`
- [ ] Valid token with `admin` role can access admin endpoints
- [ ] Valid token with `customer` role can access customer endpoints
- [ ] Valid token with `customer` role is rejected on admin-only endpoints (403)
- [ ] Token with wrong `tid` (tenant) is rejected (401)
- [ ] Token with wrong `aud` (audience) is rejected (401)
- [ ] Expired token is rejected with `token_expired` error (401)
- [ ] Token with no resolvable role returns `no_diiac_role` (403)
- [ ] Request without Authorization header returns `authentication_required` (401)
- [ ] Malformed token returns `token_invalid` (401)

## Copilot Governance Intercept

- [ ] `POST /api/intercept/request` returns `intercept_id`, `actor` lineage, and `ledger_hash`
- [ ] `POST /api/intercept/response` records response with hash in ledger
- [ ] `POST /api/intercept/approval` (approve) records approval decision in ledger
- [ ] `POST /api/intercept/approval` (reject) records rejection decision in ledger
- [ ] `POST /api/intercept/approval` (escalate) records escalation decision in ledger
- [ ] Approval endpoint rejects non-admin tokens (403)
- [ ] All intercept events appear in `GET /trust` ledger with correct actor_subject

## Actor Lineage Verification

- [ ] Actor `subject` matches Entra token `sub` claim
- [ ] Actor `name` matches Entra token `name` or `preferred_username`
- [ ] Actor `tenant_id` matches expected tenant
- [ ] Actor `token_type` is `delegated` for user tokens and `app_only` for service principals
- [ ] Actor lineage is preserved in ledger entries for all intercept/response/approval events

## Audit Trail

- [ ] `POST /admin/audit-export` includes Copilot intercept events
- [ ] Ledger entries for COPILOT_INTERCEPT include `prompt_hash` (not raw prompt)
- [ ] Ledger entries for COPILOT_RESPONSE include `response_hash` (not raw response)
- [ ] Ledger entries for COPILOT_APPROVAL include `decision` and `justification`
- [ ] All ledger entries maintain hash-chain integrity (`previous_hash` → `record_hash`)

## Existing Governance Operations

- [ ] `POST /api/llm-governed-compile` works with Entra token (admin)
- [ ] `POST /api/governed-compile` works with Entra token (admin)
- [ ] `GET /api/business-profiles` works with Entra token (admin or customer)
- [ ] `POST /api/human-input/role` works with Entra token (admin or customer)
- [ ] Verification endpoints work with Entra token (admin or customer)
- [ ] Signed export works with Entra token (admin)
- [ ] Admin endpoints work with Entra token (admin)

## Fallback and Recovery

- [ ] Setting `AUTH_MODE=` (empty) reverts to legacy header auth cleanly
- [ ] Bridge starts successfully when Entra JWKS endpoint is temporarily unreachable
- [ ] JWKS key rotation is handled automatically (jose library caches and refreshes)

## Security Hardening

- [ ] No shared secrets (`ENTRA_JWT_HS256_SECRET`) present in production environment
- [ ] Service account has least-privilege permissions
- [ ] Conditional access policies applied to DIIaC app registration
- [ ] Token lifetimes follow organisation policy
- [ ] Certificate-based auth or managed identity configured (recommended)
