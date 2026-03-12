# Dedicated Vendorlogic UI Deployment (ACA)

This folder contains dedicated Azure Container Apps IaC for the isolated Vendorlogic UI production stack.

## Scope

- Creates a dedicated resource group and dedicated runtime/bridge/frontend services.
- No overlap with existing `RG_ROOT` runtime services.
- Shares only:
  - Entra ID identities and app registrations
  - Existing Key Vault `kv-diiac-vendorlogic` (via secret references only)

## Templates

- `main.sub.bicep`: subscription-scope wrapper that creates the dedicated resource group and calls the resource-group module.
- `main.rg.bicep`: dedicated stack resources in the target resource group.
- `vendorlogic-prod.sub.bicepparam`: Vendorlogic production values.

## Deployment Stages

1. Infra-only:
   - Deploy with `deployApps=false` to create ACR, identity, log analytics, ACA environment, and RBAC.
2. Push images:
   - Build and push runtime/bridge/frontend images to the dedicated ACR.
3. Apps:
   - Deploy with `deployApps=true` to create runtime/bridge/frontend container apps.
4. Domain:
   - Bind `diiacui.vendorlogic.io` after DNS TXT/CNAME records are in place.

## Scripts

- `scripts/deploy-azure-dedicated-ui.sh`:
  - `--plan`: validate + what-if only.
  - `--apply`: apply deployment.
  - `--infra-only`: sets `deployApps=false`.
  - `--with-apps`: sets `deployApps=true`.
- `scripts/build-push-dedicated-ui-images.sh`:
  - Builds and pushes runtime/bridge/frontend images into the dedicated ACR.
