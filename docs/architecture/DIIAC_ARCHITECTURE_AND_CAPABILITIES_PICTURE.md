# Architecture And Capabilities Picture (v1.3.0-ui)

## High-Level Flow

User -> UI (`diiacui.vendorlogic.io`) -> Bridge API -> Runtime -> Artifacts/Evidence -> Verification/Audit

## Component Boundaries

- UI handles interaction and token acquisition.
- Bridge handles identity enforcement, orchestration, and policy gateways.
- Runtime performs deterministic governance computation and trust artifact generation.

## Shared Dependencies

- Microsoft Entra ID: authentication and role signal.
- Azure Key Vault: secret source for tokens and signing key material.

## Isolation

The deployed UI stack is isolated into a dedicated Azure environment with dedicated app resources.
