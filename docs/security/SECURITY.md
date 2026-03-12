# Security Policy (v1.3.0-ui)

## Scope

This policy applies to the DIIaC UI build in this repository, including:

- Frontend UI (`Frontend/`)
- Backend UI bridge (`backend-ui-bridge/`)
- Governance runtime (`app.py`)
- Azure deployment assets (`infra/`, `scripts/`)

## Security Baseline

- Identity: Microsoft Entra ID
- Auth mode: `AUTH_MODE=entra_jwt_rs256` in production
- Secrets: Key Vault only, accessed via managed identity
- Signed artifacts: Ed25519 key material sourced from Key Vault in production
- TLS: required for external endpoints

## Reporting

Report vulnerabilities through your approved internal security channel.
Include:

- Affected path/component
- Reproduction steps
- Impact level
- Suggested remediation

## Hard Rules

- Do not commit secret values to git.
- Do not disable Entra auth in production.
- Do not ship with ephemeral signing keys in production.
- Do not loosen CORS beyond approved origins.

## Operational Controls

- Pre-apply deployment what-if required.
- Post-deploy validation runbook required.
- Evidence capture required for each production checkpoint.
- Any auth/signing regression is a release blocker.
