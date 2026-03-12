targetScope = 'subscription'

@description('Dedicated resource group for the isolated UI production deployment.')
param resourceGroupName string

@description('Azure region for the dedicated resource group and child resources.')
param resourceGroupLocation string

@description('Set false to deploy shared infra only (ACR, identity, logs, ACA env, RBAC), without container apps.')
param deployApps bool = true

@description('Name of the dedicated ACR for this UI deployment.')
param containerRegistryName string

@description('Name of the dedicated user-assigned managed identity.')
param managedIdentityName string

@description('Name of the dedicated Log Analytics workspace.')
param logAnalyticsWorkspaceName string

@description('Name of the dedicated storage account for persistent Container Apps volumes.')
param storageAccountName string = 'stdiiacv130vlui01'

@description('Name of the dedicated Azure Container Apps environment.')
param containerAppsEnvironmentName string

@description('Runtime container app name.')
param runtimeAppName string

@description('Bridge container app name.')
param bridgeAppName string

@description('Frontend container app name.')
param uiAppName string

@description('Existing shared Key Vault name.')
param sharedKeyVaultName string

@description('Resource group containing the shared Key Vault.')
param sharedKeyVaultResourceGroupName string

@description('Subscription containing the shared Key Vault.')
param sharedKeyVaultSubscriptionId string = subscription().subscriptionId

@description('Frontend custom domain.')
param uiPublicDomain string = 'diiacui.vendorlogic.io'

@description('Managed certificate resource ID for UI custom domain binding. Leave empty to skip binding.')
param uiCustomDomainCertificateId string = ''

@description('Subdomain host record for the frontend custom domain.')
param uiDnsSubdomain string = 'diiacui'

@description('Container image repository prefix.')
param imageRepositoryPrefix string = 'diiac'

@description('Runtime image tag.')
param runtimeImageTag string = '1.3.0-adminheaderfix'

@description('Bridge image tag.')
param bridgeImageTag string = '1.3.0-ingressfix'

@description('Frontend image tag.')
param frontendImageTag string = '1.3.0-groupmapfix'

@description('Runtime API version string reported by /admin/config.')
param runtimeAppVersion string = 'v1.3.0-ui'

@description('Entra tenant ID for auth validation.')
param entraTenantId string

@description('Entra API app registration client ID.')
param entraApiAppId string

@description('Entra UI app registration client ID.')
param entraUiAppId string

@description('Entra admin group object ID.')
param entraAdminGroupId string

@description('Entra standard group object ID.')
param entraStandardGroupId string

@description('Optional principal-to-role JSON map for app principals.')
param entraPrincipalToRoleJson string = '{}'

@description('Copilot model name.')
param copilotModel string = 'gpt-4o'

@description('Runtime CPU allocation.')
param runtimeCpu string = '0.25'

@description('Runtime memory allocation.')
param runtimeMemory string = '0.5Gi'

@description('Bridge CPU allocation.')
param bridgeCpu string = '0.25'

@description('Bridge memory allocation.')
param bridgeMemory string = '0.5Gi'

@description('Frontend CPU allocation.')
param frontendCpu string = '0.25'

@description('Frontend memory allocation.')
param frontendMemory string = '0.5Gi'

@description('Runtime scale min replicas.')
param runtimeMinReplicas int = 0

@description('Runtime scale max replicas.')
param runtimeMaxReplicas int = 1

@description('Bridge scale min replicas.')
param bridgeMinReplicas int = 0

@description('Bridge scale max replicas.')
param bridgeMaxReplicas int = 1

@description('Frontend scale min replicas.')
param uiMinReplicas int = 0

@description('Frontend scale max replicas.')
param uiMaxReplicas int = 1

resource dedicatedResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: resourceGroupLocation
}

module dedicatedStack './main.rg.bicep' = {
  name: 'dedicated-ui-stack'
  scope: dedicatedResourceGroup
  params: {
    location: resourceGroupLocation
    deployApps: deployApps
    containerRegistryName: containerRegistryName
    managedIdentityName: managedIdentityName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    storageAccountName: storageAccountName
    containerAppsEnvironmentName: containerAppsEnvironmentName
    runtimeAppName: runtimeAppName
    bridgeAppName: bridgeAppName
    uiAppName: uiAppName
    sharedKeyVaultName: sharedKeyVaultName
    sharedKeyVaultResourceGroupName: sharedKeyVaultResourceGroupName
    sharedKeyVaultSubscriptionId: sharedKeyVaultSubscriptionId
    uiPublicDomain: uiPublicDomain
    uiCustomDomainCertificateId: uiCustomDomainCertificateId
    uiDnsSubdomain: uiDnsSubdomain
    imageRepositoryPrefix: imageRepositoryPrefix
    runtimeImageTag: runtimeImageTag
    bridgeImageTag: bridgeImageTag
    frontendImageTag: frontendImageTag
    runtimeAppVersion: runtimeAppVersion
    entraTenantId: entraTenantId
    entraApiAppId: entraApiAppId
    entraUiAppId: entraUiAppId
    entraAdminGroupId: entraAdminGroupId
    entraStandardGroupId: entraStandardGroupId
    entraPrincipalToRoleJson: entraPrincipalToRoleJson
    copilotModel: copilotModel
    runtimeCpu: runtimeCpu
    runtimeMemory: runtimeMemory
    bridgeCpu: bridgeCpu
    bridgeMemory: bridgeMemory
    frontendCpu: frontendCpu
    frontendMemory: frontendMemory
    runtimeMinReplicas: runtimeMinReplicas
    runtimeMaxReplicas: runtimeMaxReplicas
    bridgeMinReplicas: bridgeMinReplicas
    bridgeMaxReplicas: bridgeMaxReplicas
    uiMinReplicas: uiMinReplicas
    uiMaxReplicas: uiMaxReplicas
  }
}

module sharedKeyVaultRole './modules/keyvault-secrets-user-role.bicep' = {
  name: 'dedicated-ui-keyvault-secrets-user'
  scope: resourceGroup(sharedKeyVaultSubscriptionId, sharedKeyVaultResourceGroupName)
  params: {
    keyVaultName: sharedKeyVaultName
    principalId: dedicatedStack.outputs.dedicatedManagedIdentityPrincipalId
  }
}

output resourceGroupName string = dedicatedResourceGroup.name
output dedicatedAcrName string = dedicatedStack.outputs.dedicatedAcrName
output dedicatedAcrLoginServer string = dedicatedStack.outputs.dedicatedAcrLoginServer
output dedicatedStorageAccountName string = dedicatedStack.outputs.dedicatedStorageAccountName
output dedicatedManagedIdentityId string = dedicatedStack.outputs.dedicatedManagedIdentityId
output dedicatedManagedIdentityPrincipalId string = dedicatedStack.outputs.dedicatedManagedIdentityPrincipalId
output dedicatedManagedEnvironmentId string = dedicatedStack.outputs.dedicatedManagedEnvironmentId
output dedicatedManagedEnvironmentDefaultDomain string = dedicatedStack.outputs.dedicatedManagedEnvironmentDefaultDomain
output sharedKeyVaultId string = dedicatedStack.outputs.sharedKeyVaultId
output sharedKeyVaultUri string = dedicatedStack.outputs.sharedKeyVaultUri
output runtimeInternalBaseUrl string = dedicatedStack.outputs.runtimeInternalBaseUrl
output bridgeExternalBaseUrl string = dedicatedStack.outputs.bridgeExternalBaseUrl
output uiAppFqdn string = dedicatedStack.outputs.uiAppFqdn
output dnsCnameHost string = dedicatedStack.outputs.dnsCnameHost
output dnsCnameTarget string = dedicatedStack.outputs.dnsCnameTarget
output dnsTxtHost string = dedicatedStack.outputs.dnsTxtHost
output dnsTxtValue string = dedicatedStack.outputs.dnsTxtValue
output uiCustomDomain string = dedicatedStack.outputs.uiCustomDomain
output sharedKeyVaultSecretsUserRoleAssignmentId string = sharedKeyVaultRole.outputs.roleAssignmentId
