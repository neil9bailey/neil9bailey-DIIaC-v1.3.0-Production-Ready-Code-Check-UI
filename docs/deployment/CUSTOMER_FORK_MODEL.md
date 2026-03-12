# Customer Fork Model (v1.3.0-ui)

This repository supports a customer-isolated deployment model while keeping one shared codebase.

## Principles

- Shared core code, customer-specific configuration overlays.
- Dedicated resource naming per customer/environment.
- Shared identity platform is allowed only where explicitly approved.
- Secrets never committed; always retrieved from customer Key Vault.

## Configuration Surfaces

- `customer-config/<customer>/config.env` for non-secret IDs and names.
- `infra/aca-dedicated-ui/*.bicepparam` for environment deployment parameters.
- `scripts/*` for safe deploy and image publishing workflows.

## Onboarding A New Customer

1. Create `customer-config/<customer>/config.env` with tenant/app/group IDs.
2. Create dedicated `*.sub.bicepparam` under `infra/aca-dedicated-ui/`.
3. Set dedicated RG/ACR/identity/app names.
4. Register DNS domain values and Entra redirect URIs.
5. Execute plan/apply checkpoints with evidence capture.

## Isolation Expectations

- Separate resource group and container apps environment per customer deployment.
- No cross-customer runtime or bridge app reuse.
- Key Vault sharing only by explicit contract and RBAC scope.
