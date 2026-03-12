# CP7 Apply Summary (Infra Only)

- UTC timestamp: 2026-03-11 21:56:04 +00:00
- Deployment: diiac-ui-dedicated-cp7-infra-20260311-215020
- Validate: SUCCESS
- What-if: SUCCESS
- Apply: SUCCESS
- What-if creates/modifies/deletes: 7 / 0 / 0
- Dedicated RG exists: true
- Container Apps in subscription: 0
- ACA environments in subscription: 1

## Created Dedicated Infra
- Microsoft.ContainerRegistry/registries/acrdiiacv130vlui
- Microsoft.ManagedIdentity/userAssignedIdentities/id-vendorlogic-ui-prod-v130
- Microsoft.OperationalInsights/workspaces/law-vendorlogic-ui-prod-v130
- Microsoft.App/managedEnvironments/acae-vendorlogic-ui-prod-v130

## Shared Resource Touchpoints
- Key Vault role assignment created for new UI managed identity (secrets read only).
- Role assignment id: /subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_ROOT/providers/Microsoft.KeyVault/vaults/kv-diiac-vendorlogic/providers/Microsoft.Authorization/roleAssignments/a9b247d1-d791-55bd-876d-55e3230771ae

## Key Outputs
- ACR login server: acrdiiacv130vlui.azurecr.io
- ACA env default domain: blackpond-85ed120f.uksouth.azurecontainerapps.io
- UI custom domain target (pending app deploy): diiacui.vendorlogic.io
