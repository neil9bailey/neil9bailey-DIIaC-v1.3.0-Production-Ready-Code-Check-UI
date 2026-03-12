targetScope = 'resourceGroup'

@description('Azure region for dedicated UI resources.')
param location string = resourceGroup().location

@description('Set false to deploy dedicated shared infra only (ACR, identity, logs, ACA env, RBAC), without container apps.')
param deployApps bool = true

@description('Name of the dedicated ACR for this UI deployment.')
param containerRegistryName string

@description('Name of the dedicated user-assigned managed identity.')
param managedIdentityName string

@description('Name of the dedicated Log Analytics workspace.')
param logAnalyticsWorkspaceName string

@description('Name of the dedicated storage account for persistent Container Apps volumes.')
param storageAccountName string

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

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 90
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource storageFileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

var persistentShareConfigs = [
  {
    storageName: 'runtime-artifacts-storage'
    shareName: 'diiac-runtime-artifacts'
  }
  {
    storageName: 'runtime-exports-storage'
    shareName: 'diiac-runtime-exports'
  }
  {
    storageName: 'runtime-audit-storage'
    shareName: 'diiac-runtime-audit'
  }
  {
    storageName: 'runtime-state-storage'
    shareName: 'diiac-runtime-state'
  }
  {
    storageName: 'bridge-human-input-storage'
    shareName: 'diiac-bridge-human-input'
  }
  {
    storageName: 'bridge-decision-packs-storage'
    shareName: 'diiac-bridge-decision-packs'
  }
  {
    storageName: 'bridge-state-storage'
    shareName: 'diiac-bridge-state'
  }
  {
    storageName: 'bridge-ledger-storage'
    shareName: 'diiac-bridge-ledger'
  }
]

resource persistentFileShares 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = [
  for cfg in persistentShareConfigs: {
    parent: storageFileService
    name: cfg.shareName
  }
]

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource acaPersistentStorages 'Microsoft.App/managedEnvironments/storages@2023-05-01' = [
  for cfg in persistentShareConfigs: {
    parent: containerAppsEnvironment
    name: cfg.storageName
    properties: {
      azureFile: {
        accountName: storageAccount.name
        accountKey: storageAccount.listKeys().keys[0].value
        shareName: cfg.shareName
        accessMode: 'ReadWrite'
      }
    }
    dependsOn: [
      persistentFileShares
    ]
  }
]

resource sharedKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: sharedKeyVaultName
  scope: resourceGroup(sharedKeyVaultSubscriptionId, sharedKeyVaultResourceGroupName)
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, managedIdentity.id, 'acrpull')
  scope: containerRegistry
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

var entraExpectedAudience = 'api://${entraApiAppId}'
var entraIssuerV2 = '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
var entraExpectedIssuers = entraIssuerV2
var entraGroupToRoleJson = '{"${entraAdminGroupId}":{"role":"admin"},"${entraStandardGroupId}":{"role":"standard"}}'
var entraOidcUrl = '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0/.well-known/openid-configuration'
var entraJwksUri = '${environment().authentication.loginEndpoint}${entraTenantId}/discovery/v2.0/keys'
var envDefaultDomain = containerAppsEnvironment.properties.defaultDomain
var runtimeInternalBaseUrl = 'https://${runtimeAppName}.internal.${envDefaultDomain}'
var bridgeExternalBaseUrl = 'https://${bridgeAppName}.${envDefaultDomain}'
var uiDefaultFqdn = 'https://${uiAppName}.${envDefaultDomain}'
var bridgeAllowedOrigins = 'https://${uiPublicDomain},${uiDefaultFqdn}'
var keyVaultSecretBaseUrl = '${sharedKeyVault.properties.vaultUri}secrets'
var runtimeArtifactsStorageName = 'runtime-artifacts-storage'
var runtimeExportsStorageName = 'runtime-exports-storage'
var runtimeAuditStorageName = 'runtime-audit-storage'
var runtimeStateStorageName = 'runtime-state-storage'
var bridgeHumanInputStorageName = 'bridge-human-input-storage'
var bridgeDecisionPacksStorageName = 'bridge-decision-packs-storage'
var bridgeStateStorageName = 'bridge-state-storage'
var bridgeLedgerStorageName = 'bridge-ledger-storage'

resource runtimeApp 'Microsoft.App/containerApps@2023-05-01' = if (deployApps) {
  name: runtimeAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        allowInsecure: false
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'admin-api-token'
          keyVaultUrl: '${keyVaultSecretBaseUrl}/diiac-admin-api-token'
          identity: managedIdentity.id
        }
        {
          name: 'signing-private-key-pem'
          keyVaultUrl: '${keyVaultSecretBaseUrl}/diiac-signing-private-key-pem'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'governance-runtime'
          image: '${containerRegistry.properties.loginServer}/${imageRepositoryPrefix}/governance-runtime:${runtimeImageTag}'
          env: [
            {
              name: 'APP_ENV'
              value: 'production'
            }
            {
              name: 'ADMIN_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'STRICT_DETERMINISTIC_MODE'
              value: 'true'
            }
            {
              name: 'SIGNING_ENABLED'
              value: 'true'
            }
            {
              name: 'SIGNING_KEY_ID'
              value: 'diiac-vendorlogic-prod'
            }
            {
              name: 'APP_VERSION'
              value: runtimeAppVersion
            }
            {
              name: 'DIIAC_SQLITE_NOLOCK'
              value: 'true'
            }
            {
              name: 'LLM_PROVIDER_MODE'
              value: 'copilot_only'
            }
            {
              name: 'ADMIN_API_TOKEN'
              secretRef: 'admin-api-token'
            }
            {
              name: 'SIGNING_PRIVATE_KEY_PEM'
              secretRef: 'signing-private-key-pem'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 20
              periodSeconds: 20
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
          volumeMounts: [
            {
              volumeName: 'runtime-artifacts-volume'
              mountPath: '/app/artifacts'
            }
            {
              volumeName: 'runtime-exports-volume'
              mountPath: '/app/exports'
            }
            {
              volumeName: 'runtime-audit-volume'
              mountPath: '/app/audit_exports'
            }
            {
              volumeName: 'runtime-state-volume'
              mountPath: '/app/state'
            }
          ]
          resources: {
            cpu: json(runtimeCpu)
            memory: runtimeMemory
          }
        }
      ]
      volumes: [
        {
          name: 'runtime-artifacts-volume'
          storageType: 'AzureFile'
          storageName: runtimeArtifactsStorageName
        }
        {
          name: 'runtime-exports-volume'
          storageType: 'AzureFile'
          storageName: runtimeExportsStorageName
        }
        {
          name: 'runtime-audit-volume'
          storageType: 'AzureFile'
          storageName: runtimeAuditStorageName
        }
        {
          name: 'runtime-state-volume'
          storageType: 'AzureFile'
          storageName: runtimeStateStorageName
        }
      ]
      scale: {
        minReplicas: runtimeMinReplicas
        maxReplicas: runtimeMaxReplicas
      }
    }
  }
  dependsOn: [
    acrPullRole
    acaPersistentStorages
  ]
}

resource bridgeApp 'Microsoft.App/containerApps@2023-05-01' = if (deployApps) {
  name: bridgeAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3001
        allowInsecure: false
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'admin-api-token'
          keyVaultUrl: '${keyVaultSecretBaseUrl}/diiac-admin-api-token'
          identity: managedIdentity.id
        }
        {
          name: 'signing-private-key-pem'
          keyVaultUrl: '${keyVaultSecretBaseUrl}/diiac-signing-private-key-pem'
          identity: managedIdentity.id
        }
        {
          name: 'github-token'
          keyVaultUrl: '${keyVaultSecretBaseUrl}/diiac-github-token'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend-ui-bridge'
          image: '${containerRegistry.properties.loginServer}/${imageRepositoryPrefix}/backend-ui-bridge:${bridgeImageTag}'
          env: [
            {
              name: 'APP_ENV'
              value: 'production'
            }
            {
              name: 'PYTHON_BASE_URL'
              value: runtimeInternalBaseUrl
            }
            {
              name: 'STRICT_DETERMINISTIC_MODE'
              value: 'true'
            }
            {
              name: 'SIGNING_ENABLED'
              value: 'true'
            }
            {
              name: 'SIGNING_KEY_ID'
              value: 'diiac-vendorlogic-prod'
            }
            {
              name: 'SIGNING_PRIVATE_KEY_PEM'
              secretRef: 'signing-private-key-pem'
            }
            {
              name: 'LLM_INGESTION_ENABLED'
              value: 'true'
            }
            {
              name: 'LLM_STUB_ENABLED'
              value: 'false'
            }
            {
              name: 'LLM_PROVIDER_MODE'
              value: 'copilot_only'
            }
            {
              name: 'COPILOT_MODEL'
              value: copilotModel
            }
            {
              name: 'ALLOWED_ORIGINS'
              value: bridgeAllowedOrigins
            }
            {
              name: 'AUTH_MODE'
              value: 'entra_jwt_rs256'
            }
            {
              name: 'ENTRA_ROLE_CLAIM'
              value: 'roles'
            }
            {
              name: 'ENTRA_EXPECTED_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'ENTRA_EXPECTED_AUDIENCE'
              value: entraExpectedAudience
            }
            {
              name: 'ENTRA_EXPECTED_ISSUERS'
              value: entraExpectedIssuers
            }
            {
              name: 'ENTRA_GROUP_TO_ROLE_JSON'
              value: entraGroupToRoleJson
            }
            {
              name: 'ENTRA_PRINCIPAL_TO_ROLE_JSON'
              value: entraPrincipalToRoleJson
            }
            {
              name: 'ENTRA_OIDC_DISCOVERY_URL'
              value: entraOidcUrl
            }
            {
              name: 'ENTRA_JWKS_URI'
              value: entraJwksUri
            }
            {
              name: 'ADMIN_API_TOKEN'
              secretRef: 'admin-api-token'
            }
            {
              name: 'GITHUB_TOKEN'
              secretRef: 'github-token'
            }
            {
              name: 'BRIDGE_STATE_PATH'
              value: '/workspace/state/operations_state.json'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 3001
              }
              initialDelaySeconds: 20
              periodSeconds: 20
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/readiness'
                port: 3001
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
          volumeMounts: [
            {
              volumeName: 'bridge-human-input-volume'
              mountPath: '/workspace/artefacts/human-input'
            }
            {
              volumeName: 'bridge-decision-packs-volume'
              mountPath: '/workspace/artefacts/decision-packs'
            }
            {
              volumeName: 'bridge-state-volume'
              mountPath: '/workspace/state'
            }
            {
              volumeName: 'bridge-ledger-volume'
              mountPath: '/workspace/ledger'
            }
          ]
          resources: {
            cpu: json(bridgeCpu)
            memory: bridgeMemory
          }
        }
      ]
      volumes: [
        {
          name: 'bridge-human-input-volume'
          storageType: 'AzureFile'
          storageName: bridgeHumanInputStorageName
        }
        {
          name: 'bridge-decision-packs-volume'
          storageType: 'AzureFile'
          storageName: bridgeDecisionPacksStorageName
        }
        {
          name: 'bridge-state-volume'
          storageType: 'AzureFile'
          storageName: bridgeStateStorageName
        }
        {
          name: 'bridge-ledger-volume'
          storageType: 'AzureFile'
          storageName: bridgeLedgerStorageName
        }
      ]
      scale: {
        minReplicas: bridgeMinReplicas
        maxReplicas: bridgeMaxReplicas
      }
    }
  }
  dependsOn: [
    runtimeApp
  ]
}

resource uiApp 'Microsoft.App/containerApps@2023-05-01' = if (deployApps) {
  name: uiAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 5173
        allowInsecure: false
        transport: 'auto'
        customDomains: empty(uiCustomDomainCertificateId)
          ? []
          : [
              {
                name: uiPublicDomain
                bindingType: 'SniEnabled'
                certificateId: uiCustomDomainCertificateId
              }
            ]
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${containerRegistry.properties.loginServer}/${imageRepositoryPrefix}/frontend:${frontendImageTag}'
          env: [
            {
              name: 'APP_ENV'
              value: 'production'
            }
            {
              name: 'VITE_API_BASE'
              value: bridgeExternalBaseUrl
            }
            {
              name: 'VITE_LLM_PROVIDER_MODE'
              value: 'copilot_only'
            }
            {
              name: 'VITE_ENTRA_CLIENT_ID'
              value: entraUiAppId
            }
            {
              name: 'VITE_ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'VITE_ENTRA_REDIRECT_URI'
              value: 'https://${uiPublicDomain}/auth/callback'
            }
            {
              name: 'VITE_ENTRA_GROUP_MAP'
              value: entraGroupToRoleJson
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/'
                port: 5173
              }
              initialDelaySeconds: 20
              periodSeconds: 20
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/'
                port: 5173
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
          resources: {
            cpu: json(frontendCpu)
            memory: frontendMemory
          }
        }
      ]
      scale: {
        minReplicas: uiMinReplicas
        maxReplicas: uiMaxReplicas
      }
    }
  }
  dependsOn: [
    bridgeApp
  ]
}

output resourceGroupName string = resourceGroup().name
output dedicatedAcrName string = containerRegistry.name
output dedicatedAcrLoginServer string = containerRegistry.properties.loginServer
output dedicatedStorageAccountName string = storageAccount.name
output dedicatedManagedIdentityId string = managedIdentity.id
output dedicatedManagedIdentityPrincipalId string = managedIdentity.properties.principalId
output dedicatedManagedEnvironmentId string = containerAppsEnvironment.id
output dedicatedManagedEnvironmentDefaultDomain string = containerAppsEnvironment.properties.defaultDomain
output sharedKeyVaultId string = sharedKeyVault.id
output sharedKeyVaultUri string = sharedKeyVault.properties.vaultUri
output runtimeInternalBaseUrl string = deployApps ? runtimeInternalBaseUrl : ''
output bridgeExternalBaseUrl string = deployApps ? bridgeExternalBaseUrl : ''
output uiAppFqdn string = deployApps ? uiApp!.properties.configuration.ingress.fqdn : ''
output dnsCnameHost string = uiDnsSubdomain
output dnsCnameTarget string = deployApps ? uiApp!.properties.configuration.ingress.fqdn : ''
output dnsTxtHost string = 'asuid.${uiDnsSubdomain}'
output dnsTxtValue string = deployApps ? uiApp!.properties.customDomainVerificationId : ''
output uiCustomDomain string = uiPublicDomain
