using './main.sub.bicep'

param resourceGroupName = 'RG_UI_VENDORLOGIC_PROD_V130'
param resourceGroupLocation = 'uksouth'

// Stage control: defaults to infra-only for safety.
param deployApps = false

// Dedicated resource names (no overlap with existing RG_ROOT resources).
param containerRegistryName = 'acrdiiacv130vlui'
param managedIdentityName = 'id-vendorlogic-ui-prod-v130'
param logAnalyticsWorkspaceName = 'law-vendorlogic-ui-prod-v130'
param storageAccountName = 'stdiiacv130vlui01'
param containerAppsEnvironmentName = 'acae-vendorlogic-ui-prod-v130'
param runtimeAppName = 'rt-vendorlogic-ui-prod-v130'
param bridgeAppName = 'br-vendorlogic-ui-prod-v130'
param uiAppName = 'ui-vendorlogic-ui-prod-v130'

// Shared components allowed by contract.
param sharedKeyVaultName = 'kv-diiac-vendorlogic'
param sharedKeyVaultResourceGroupName = 'RG_ROOT'
param sharedKeyVaultSubscriptionId = '3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7'

// External access target.
param uiPublicDomain = 'diiacui.vendorlogic.io'
param uiCustomDomainCertificateId = '/subscriptions/3ed9fa77-6bf2-4ffc-bd67-f5a442d3e5e7/resourceGroups/RG_UI_VENDORLOGIC_PROD_V130/providers/Microsoft.App/managedEnvironments/acae-vendorlogic-ui-prod-v130/managedCertificates/mc-acae-vendorlog-diiacui-vendorlo-1321'
param uiDnsSubdomain = 'diiacui'

// Image coordinates (dedicated ACR destination).
param imageRepositoryPrefix = 'diiac'
param runtimeImageTag = '1.3.0-ab41660-closure'
param bridgeImageTag = '1.3.0-ab41660-closure'
param frontendImageTag = '1.3.0-ab41660-closure'
param runtimeAppVersion = 'v1.3.0-ui'

// Entra / auth config.
param entraTenantId = '1384b1c5-2bae-45a1-a4b4-e94e3315eb41'
param entraApiAppId = 'b726558d-f1c6-48f7-8a3d-72d5db818d0f'
param entraUiAppId = 'b726558d-f1c6-48f7-8a3d-72d5db818d0f'
param entraAdminGroupId = '81786818-de16-4115-b061-92fce74b00bd'
param entraStandardGroupId = '9c7dd0d4-5b44-4811-b167-e52df21092d8'
param entraPrincipalToRoleJson = '{"b726558d-f1c6-48f7-8a3d-72d5db818d0f":"admin","2f1a1479-90d3-4f46-8107-f9b3f90b0cf7":"admin"}'
param copilotModel = 'gpt-4o'

// Sizing mirrors current production app profile.
param runtimeCpu = '0.25'
param runtimeMemory = '0.5Gi'
param bridgeCpu = '0.25'
param bridgeMemory = '0.5Gi'
param frontendCpu = '0.25'
param frontendMemory = '0.5Gi'

param runtimeMinReplicas = 0
param runtimeMaxReplicas = 1
param bridgeMinReplicas = 0
param bridgeMaxReplicas = 1
param uiMinReplicas = 0
param uiMaxReplicas = 1
