# Release Notes (Maintained Reference, v1.3.0-ui)

Note: filename retains `v1.2.0` for continuity; this document now summarizes the current release posture.

## Release Summary

`v1.3.0-ui` establishes the Azure production-ready UI stack baseline with:

- Dedicated ACA deployment topology
- Entra production auth alignment
- Key Vault-only secret handling
- Custom-domain public access
- Updated deployment and validation runbooks

## Highlights

- Entra redirect URI mismatch issue resolved by aligning callback URI to custom domain.
- Bridge auth mode validated as Entra RS256 production mode.
- Governance decision output quality validated through checkpoint evidence process.

## Upgrade Impact

- Deployment docs now prioritize dedicated ACA templates and scripts.
- Legacy ACI templates remain for backward reference only.

## Known Constraints

- Role mapping depends on correct Entra group claims or configured app roles.
- DNS propagation timing affects custom domain verification and certificate readiness.
