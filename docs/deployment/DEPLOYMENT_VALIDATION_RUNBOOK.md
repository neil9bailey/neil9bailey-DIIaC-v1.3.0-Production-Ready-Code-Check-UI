# Deployment Validation Runbook (v1.3.0-ui)

Run this after each Azure deployment or image rollout.

## A. Platform Health

1. Check UI endpoint returns HTTP 200 at `https://diiacui.vendorlogic.io`.
2. Check bridge health/auth endpoint.
3. Check runtime health/readiness endpoints.
4. Confirm container app revisions are healthy and active.

## B. Identity And RBAC

1. Validate Entra login from UI.
2. Validate bridge reports auth mode `entra_jwt_rs256`.
3. Validate admin group users receive admin capabilities.
4. Validate standard users are constrained correctly.

## C. Governance Functional Checks

1. Submit role/intent input.
2. Run compile/decision flow.
3. Verify execution trace, scoring, and trust endpoints.
4. Download decision pack and signed exports.

## D. Security Checks

1. Confirm no secret values in app env except Key Vault secret references.
2. Confirm managed identity has required Key Vault Secrets User role.
3. Confirm TLS on external endpoints.
4. Confirm CORS `ALLOWED_ORIGINS` includes only intended origins.

## E. Evidence Capture

Store validation artifacts under:

- `docs/release/evidence/<date-or-checkpoint>/`

Minimum evidence:

- Deployment outputs
- What-if output used before apply
- Endpoint probes
- Auth status snapshots
- Execution quality summary

## F. Go/No-Go

Go if all A-E pass with no P1/P2 issues. Otherwise stop rollout and remediate.
