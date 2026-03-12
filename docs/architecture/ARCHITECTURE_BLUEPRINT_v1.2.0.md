# Architecture Blueprint (Maintained Reference, v1.3.0-ui)

Note: filename is legacy (`v1.2.0`) for continuity.
For the full implementation-level design, use:
`docs/architecture/DIIAC_CURRENT_ARCHITECTURE_BLUEPRINT.md`.

## Logical Layers

1. Experience Layer
- React UI dashboard and workflow views.

2. Governance Orchestration Layer
- Bridge APIs, request validation, auth/RBAC, and provider orchestration.

3. Deterministic Governance Core
- Runtime scoring, policy enforcement, trust ledger, signatures.

4. Integrity And Audit Layer
- Merkle/hash chain, signed manifests, export + verification.

## Deployment Pattern

- Dedicated Azure Container Apps stack per production environment.
- Managed identity for ACR pull and Key Vault secret access.
- Key Vault stores secret values only.
- External UI domain backed by ACA custom domain and TLS cert.

## Compatibility Note

Legacy ACI IaC exists for reference, but dedicated ACA is the active production pattern.
