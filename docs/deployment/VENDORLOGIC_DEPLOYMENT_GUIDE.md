# Vendorlogic Deployment Guide (Dedicated ACA, v1.3.0-ui)

This is the authoritative production deployment flow for Vendorlogic UI in Azure.

## Deployment Contract

- Dedicated resource group and dedicated ACA environment for UI stack.
- No overlap with unrelated production workloads.
- Shared services allowed:
  - Microsoft Entra ID
  - Existing Key Vault: `kv-diiac-vendorlogic`
- Secrets remain in Key Vault only.

## Inputs

- Subscription: `3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7`
- Tenant: `1384b1c5-2bae-45a1-a4b4-e94e3315eb41`
- Param file: `infra/aca-dedicated-ui/vendorlogic-prod.sub.bicepparam`

## Phase 1: Infra Plan (safe)

```bash
bash scripts/deploy-azure-dedicated-ui.sh --plan --infra-only
```

Outputs are captured under `docs/release/evidence/2026-03-11-ui-dedicated-azure/`.

## Phase 2: Infra Apply

```bash
bash scripts/deploy-azure-dedicated-ui.sh --apply --infra-only
```

Creates dedicated RG + ACR + managed identity + log analytics + ACA environment + RBAC.

## Phase 3: Build And Push Images

```bash
bash scripts/build-push-dedicated-ui-images.sh \
  --acr-name acrdiiacv130vlui \
  --runtime-tag 1.3.0-adminheaderfix \
  --bridge-tag 1.3.0-ingressfix \
  --frontend-tag 1.3.0-groupmapfix
```

## Phase 4: Apps Plan (safe)

```bash
bash scripts/deploy-azure-dedicated-ui.sh --plan --with-apps
```

## Phase 5: Apps Apply

```bash
bash scripts/deploy-azure-dedicated-ui.sh --apply --with-apps
```

## Phase 6: Domain Binding

Deploy outputs provide DNS records:

- `dnsCnameHost`
- `dnsCnameTarget`
- `dnsTxtHost`
- `dnsTxtValue`

After DNS propagation, bind/verify custom domain for the UI Container App.

Target external domain:

- `diiacui.vendorlogic.io`

## Phase 7: Post-Deploy Validation

- UI responds over HTTPS at custom domain.
- Entra sign-in succeeds with correct redirect URI.
- Bridge auth status reports `entra_jwt_rs256`.
- Runtime health and trust endpoints are healthy.
- Governance execution produces signed artifacts and expected evidence outputs.

Use `docs/deployment/DEPLOYMENT_VALIDATION_RUNBOOK.md` for the full checklist.

## Rollback Approach

- Keep previous image tags available in ACR.
- Redeploy apps with prior known-good tags in param/override values.
- Do not delete Key Vault or shared identity dependencies during rollback.
