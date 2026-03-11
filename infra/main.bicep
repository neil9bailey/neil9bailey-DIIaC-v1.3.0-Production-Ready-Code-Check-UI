// DIIaC v1.2.0 — Azure Landing Zone Blueprint
// Provisions all infrastructure for a customer production instance.
//
// Deploy:
//   az deployment group create \
//     --resource-group rg-diiac-prod \
//     --template-file infra/main.bicep \
//     --parameters infra/main.bicepparam
//
// Resources created:
//   - Azure Container Registry (ACR)
//   - Azure Container Instances (ACI) container group (3 containers)
//   - Azure Key Vault (with RBAC)
//   - Azure File Shares for persistent volumes
//   - Storage Account for file shares
//   - User-assigned Managed Identity (ACI → Key Vault, ACI → ACR)
//   - Log Analytics workspace for container logs

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────────────────────

@description('Customer short name (lowercase, no spaces). Used in resource naming.')
param customerName string

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('DIIaC platform version tag for container images.')
param diiacVersion string = '1.2.0'

@description('Entra ID Tenant ID for JWT validation.')
param entraTenantId string

@description('Entra ID API App Registration Client ID.')
param entraApiAppId string

@description('Entra ID UI App Registration Client ID.')
param entraUiAppId string

@description('Entra Admin Group Object ID.')
param entraAdminGroupId string

@description('Entra Standard User Group Object ID.')
param entraStandardGroupId string

@description('OpenAI model to use for LLM ingestion.')
param openaiModel string = 'gpt-4o-mini'

@description('Copilot model to use (GitHub Models API).')
param copilotModel string = 'gpt-4o'

@description('Public DNS label for the container group (becomes <label>.<region>.azurecontainer.io).')
param dnsLabel string = 'diiac-${customerName}'

@description('CPU cores for governance runtime container.')
param runtimeCpu string = '0.5'

@description('Memory (GB) for governance runtime container.')
param runtimeMemory string = '1.0'

@description('CPU cores for backend bridge container.')
param bridgeCpu string = '0.5'

@description('Memory (GB) for backend bridge container.')
param bridgeMemory string = '1.0'

@description('CPU cores for frontend container.')
param frontendCpu string = '0.25'

@description('Memory (GB) for frontend container.')
param frontendMemory string = '0.5'

// ── Naming ──────────────────────────────────────────────────────────────────

var suffix = uniqueString(resourceGroup().id, customerName)
var acrName = 'acrdiiac${suffix}'
var kvName = 'kv-diiac-${customerName}'
var storageName = 'stdiiac${suffix}'
var identityName = 'id-diiac-${customerName}'
var lawName = 'law-diiac-${customerName}'
var aciName = 'aci-diiac-${customerName}'

// ── Managed Identity ────────────────────────────────────────────────────────

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

// ── Log Analytics ───────────────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: lawName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
  }
}

// ── Container Registry ──────────────────────────────────────────────────────

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

// ACR Pull role for managed identity
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, managedIdentity.id, 'acrpull')
  scope: acr
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
  }
}

// ── Key Vault ───────────────────────────────────────────────────────────────

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
  }
}

// Key Vault Secrets User role for managed identity
resource kvSecretsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'kvsecrets')
  scope: keyVault
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
  }
}

// ── Storage Account + File Shares ───────────────────────────────────────────

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

var shareNames = ['artifacts', 'exports', 'audit-exports', 'human-input', 'ledger', 'state']

resource fileShares 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = [for share in shareNames: {
  parent: fileService
  name: 'diiac-${share}'
}]

// ── Container Group (ACI) ───────────────────────────────────────────────────

var entraExpectedAudience = 'api://${entraApiAppId}'
var entraExpectedIssuers = 'https://login.microsoftonline.com/${entraTenantId}/v2.0,https://sts.windows.net/${entraTenantId}/'
var entraGroupToRoleJson = '{"${entraAdminGroupId}":{"role":"admin"},"${entraStandardGroupId}":{"role":"standard"}}'
var entraOidcUrl = 'https://login.microsoftonline.com/${entraTenantId}/v2.0/.well-known/openid-configuration'
var entraJwksUri = 'https://login.microsoftonline.com/${entraTenantId}/discovery/v2.0/keys'

resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: aciName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    osType: 'Linux'
    restartPolicy: 'Always'
    ipAddress: {
      type: 'Public'
      dnsNameLabel: dnsLabel
      ports: [
        { port: 443, protocol: 'TCP' }
        { port: 80, protocol: 'TCP' }
      ]
    }
    imageRegistryCredentials: [
      {
        server: acr.properties.loginServer
        identity: managedIdentity.id
      }
    ]
    diagnostics: {
      logAnalytics: {
        workspaceId: logAnalytics.properties.customerId
        workspaceKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    volumes: [for (share, i) in shareNames: {
      name: share
      azureFile: {
        shareName: 'diiac-${share}'
        storageAccountName: storageAccount.name
        storageAccountKey: storageAccount.listKeys().keys[0].value
        readOnly: false
      }
    }]
    containers: [
      // ── Governance Runtime (Python Flask on port 8000) ──────────────
      {
        name: 'governance-runtime'
        properties: {
          image: '${acr.properties.loginServer}/diiac/governance-runtime:${diiacVersion}'
          ports: []
          resources: {
            requests: { cpu: json(runtimeCpu), memoryInGB: json(runtimeMemory) }
          }
          environmentVariables: [
            { name: 'APP_ENV', value: 'production' }
            { name: 'ADMIN_AUTH_ENABLED', value: 'true' }
            { name: 'STRICT_DETERMINISTIC_MODE', value: 'true' }
            { name: 'SIGNING_ENABLED', value: 'true' }
            { name: 'SIGNING_KEY_ID', value: 'diiac-${customerName}-prod' }
            // Secrets injected via Key Vault reference init container or sidecar
            { name: 'ADMIN_API_TOKEN', secureValue: '' } // populated by deploy script
            { name: 'SIGNING_PRIVATE_KEY_PEM', secureValue: '' } // populated by deploy script
          ]
          volumeMounts: [
            { name: 'artifacts', mountPath: '/app/artifacts' }
            { name: 'exports', mountPath: '/app/exports' }
            { name: 'audit-exports', mountPath: '/app/audit_exports' }
            { name: 'human-input', mountPath: '/app/human_input' }
            { name: 'ledger', mountPath: '/workspace/ledger' }
            { name: 'state', mountPath: '/app/state' }
          ]
        }
      }
      // ── Backend UI Bridge (Node.js on port 3001) ────────────────────
      {
        name: 'backend-ui-bridge'
        properties: {
          image: '${acr.properties.loginServer}/diiac/backend-ui-bridge:${diiacVersion}'
          ports: []
          resources: {
            requests: { cpu: json(bridgeCpu), memoryInGB: json(bridgeMemory) }
          }
          environmentVariables: [
            { name: 'APP_ENV', value: 'production' }
            { name: 'PYTHON_BASE_URL', value: 'http://localhost:8000' }
            { name: 'STRICT_DETERMINISTIC_MODE', value: 'true' }
            { name: 'SIGNING_ENABLED', value: 'true' }
            { name: 'LLM_INGESTION_ENABLED', value: 'true' }
            { name: 'LLM_STUB_ENABLED', value: 'false' }
            { name: 'OPENAI_MODEL', value: openaiModel }
            { name: 'COPILOT_MODEL', value: copilotModel }
            { name: 'AUTH_MODE', value: 'entra_jwt_rs256' }
            { name: 'ENTRA_ROLE_CLAIM', value: 'groups' }
            { name: 'ENTRA_EXPECTED_TENANT_ID', value: entraTenantId }
            { name: 'ENTRA_EXPECTED_AUDIENCE', value: entraExpectedAudience }
            { name: 'ENTRA_EXPECTED_ISSUERS', value: entraExpectedIssuers }
            { name: 'ENTRA_GROUP_TO_ROLE_JSON', value: entraGroupToRoleJson }
            { name: 'ENTRA_OIDC_DISCOVERY_URL', value: entraOidcUrl }
            { name: 'ENTRA_JWKS_URI', value: entraJwksUri }
            // Secrets injected by deploy script
            { name: 'OPENAI_API_KEY', secureValue: '' }
            { name: 'GITHUB_TOKEN', secureValue: '' }
            { name: 'ADMIN_API_TOKEN', secureValue: '' }
          ]
        }
      }
      // ── Frontend (Vite/Nginx on port 80 → exposed) ─────────────────
      {
        name: 'frontend'
        properties: {
          image: '${acr.properties.loginServer}/diiac/frontend:${diiacVersion}'
          ports: [
            { port: 80, protocol: 'TCP' }
          ]
          resources: {
            requests: { cpu: json(frontendCpu), memoryInGB: json(frontendMemory) }
          }
          environmentVariables: [
            { name: 'VITE_API_BASE', value: 'https://${dnsLabel}.${location}.azurecontainer.io' }
            { name: 'VITE_ENTRA_CLIENT_ID', value: entraUiAppId }
            { name: 'VITE_ENTRA_TENANT_ID', value: entraTenantId }
            { name: 'VITE_ENTRA_REDIRECT_URI', value: 'https://${dnsLabel}.${location}.azurecontainer.io/auth/callback' }
            { name: 'VITE_ENTRA_GROUP_MAP', value: entraGroupToRoleJson }
          ]
        }
      }
    ]
  }
  dependsOn: [fileShares, acrPullRole, kvSecretsRole]
}

// ── Outputs ─────────────────────────────────────────────────────────────────

output acrLoginServer string = acr.properties.loginServer
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
output storageAccountName string = storageAccount.name
output containerGroupFqdn string = containerGroup.properties.ipAddress.fqdn
output logAnalyticsWorkspaceId string = logAnalytics.properties.customerId
