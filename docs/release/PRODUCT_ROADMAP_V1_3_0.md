# Product Roadmap v1.3.0

## Delivered In Current Build

- Dedicated Azure Container Apps deployment model for Vendorlogic UI stack.
- External custom-domain UI access with Entra sign-in.
- Key Vault-backed production secret posture.
- Updated documentation baseline and operational runbooks.

## Near-Term Roadmap

1. Improve deployment automation ergonomics (single command orchestration with safe gates).
2. Expand UI-side governance quality visualizations and confidence explainability.
3. Add stronger pack validation diff tooling for audit comparability.
4. Improve role diagnostics for mixed group/role claim scenarios.

## Medium-Term Roadmap

1. Multi-environment promotion contract with stricter provenance checks.
2. Enhanced policy extension lifecycle tooling.
3. Deeper telemetry correlation across UI, bridge, and runtime components.

## Non-Goals For This Cycle

- Reintroducing legacy insecure auth paths in production.
- Moving secrets out of Key Vault.
