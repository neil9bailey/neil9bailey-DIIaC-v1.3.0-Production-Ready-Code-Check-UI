# CP3 - Dedicated Deployment Assets Implemented (No Apply)

Date: 2026-03-11
Status: Completed

## What was implemented

1. Dedicated subscription-scope deployment wrapper:
   - `infra/aca-dedicated-ui/main.sub.bicep`
2. Dedicated resource-group stack template:
   - `infra/aca-dedicated-ui/main.rg.bicep`
3. Cross-scope shared Key Vault RBAC module:
   - `infra/aca-dedicated-ui/modules/keyvault-secrets-user-role.bicep`
4. Vendorlogic production parameter file:
   - `infra/aca-dedicated-ui/vendorlogic-prod.sub.bicepparam`
5. Dedicated deployment documentation:
   - `infra/aca-dedicated-ui/README.md`
6. Safe deployment orchestrator script:
   - `scripts/deploy-azure-dedicated-ui.sh`
7. Dedicated image build/push script:
   - `scripts/build-push-dedicated-ui-images.sh`

## Safety controls embedded

1. Dedicated resource names and dedicated target RG only.
2. Shared component boundary preserved:
   - Entra ID and `kv-diiac-vendorlogic` only.
3. `deployApps` stage gate is supported and defaults to `false` in Vendorlogic params.
4. Secrets are Key Vault references only (no secret values committed).

## Validation evidence

1. Bicep compile outputs:
   - `cp3_main_rg_compiled.json`
   - `cp3_main_sub_compiled.json`
2. Script syntax checks:
   - `cp3_deploy_script_syntax.txt`
   - `cp3_buildpush_script_syntax.txt`
3. Secret reference scan:
   - `cp3_secret_reference_scan.txt`
4. Asset inventory and hashes:
   - `cp3_infra_asset_inventory.txt`
   - `cp3_changed_files.txt`
   - `cp3_file_hashes_sha256.txt`

## No apply confirmation

No deployment create/apply command was executed in CP3.
