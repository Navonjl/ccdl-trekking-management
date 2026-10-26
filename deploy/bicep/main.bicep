// Head in the Clouds: the Azure infrastructure from deploy/azure/*.sh as one
// Bicep template. Deploying it to the resource group the scripts built is a
// no-op, which `az deployment group what-if` shows before anything changes.
//
// Data-plane steps stay in the scripts: secrets in Key Vault, the image build,
// the Helm release (which includes the ingress), cert-manager, the static
// website upload and role assignments.

targetScope = 'resourceGroup'

@description('Region for every resource except the global Front Door pieces.')
param location string = resourceGroup().location

@description('Prefix for names that must be globally unique.')
@minLength(5)
@maxLength(12)
param prefix string = 'hitc602'

@description('PostgreSQL administrator password. Never stored in the template.')
@secure()
param pgAdminPassword string

@description('Where Azure Monitor sends alert e-mail.')
param alertEmail string

// --- Network ------------------------------------------------------------------

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'hitc-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.20.0.0/16'] }
    subnets: [
      {
        name: 'aks'
        properties: { addressPrefix: '10.20.0.0/22' }
      }
      {
        name: 'postgres'
        properties: {
          addressPrefix: '10.20.8.0/24'
          serviceEndpoints: [{ service: 'Microsoft.Storage' }]
          delegations: [
            {
              name: '0'
              properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' }
            }
          ]
        }
      }
    ]
  }
}

resource pgZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'hitcdb.private.postgres.database.azure.com'
  location: 'global'
}

resource pgZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: pgZone
  name: 'hitc-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: vnet.id }
  }
}

// --- Registry and logs --------------------------------------------------------

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${prefix}acr'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'hitc-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    // Stays inside the free 5 GB a month.
    workspaceCapping: { dailyQuotaGb: json('0.15') }
  }
}

// --- AKS ----------------------------------------------------------------------

resource aks 'Microsoft.ContainerService/managedClusters@2026-05-01' = {
  name: 'hitc-aks'
  location: location
  sku: { name: 'Base', tier: 'Free' }
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: 'hitc-aks-hitc-rg-${substring(subscription().subscriptionId, 0, 6)}'
    agentPoolProfiles: [
      {
        name: 'nodepool1'
        mode: 'System'
        vmSize: 'Standard_B2s_v2'
        count: 1
        enableAutoScaling: true
        minCount: 1
        maxCount: 2
        osType: 'Linux'
        vnetSubnetID: vnet.properties.subnets[0].id
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
    }
    // Application routing add-on: Azure's managed NGINX ingress, the public
    // entry point (Front Door is not available on student subscriptions).
    ingressProfile: { webAppRouting: { enabled: true, nginx: { defaultIngressControllerType: 'None' } } }
    oidcIssuerProfile: { enabled: true }
    securityProfile: { workloadIdentity: { enabled: true } }
    workloadAutoScalerProfile: { keda: { enabled: true } }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: { logAnalyticsWorkspaceResourceID: logs.id }
      }
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: { enableSecretRotation: 'true' }
      }
    }
  }
}

// --- PostgreSQL ---------------------------------------------------------------

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: '${prefix}-pg'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '17'
    administratorLogin: 'hitcadmin'
    administratorLoginPassword: pgAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    network: {
      delegatedSubnetResourceId: vnet.properties.subnets[1].id
      privateDnsZoneArmResourceId: pgZone.id
    }
    highAvailability: { mode: 'Disabled' }
  }
  dependsOn: [pgZoneLink]
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: 'hitc'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// --- Azure Managed Redis --------------------------------------------------------

resource redis 'Microsoft.Cache/redisEnterprise@2025-07-01' = {
  name: '${prefix}-redis'
  location: location
  sku: { name: 'Balanced_B0' }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource redisDb 'Microsoft.Cache/redisEnterprise/databases@2025-07-01' = {
  parent: redis
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'
    port: 10000
    clusteringPolicy: 'EnterpriseCluster'
    evictionPolicy: 'VolatileLRU'
    accessKeysAuthentication: 'Enabled'
  }
}

// --- Service Bus ----------------------------------------------------------------

resource bus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: '${prefix}bus'
  location: location
  sku: { name: 'Basic', tier: 'Basic' }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: bus
  name: 'celery'
  properties: {
    maxDeliveryCount: 5
    lockDuration: 'PT5M'
    deadLetteringOnMessageExpiration: true
  }
}

// --- Storage --------------------------------------------------------------------

resource storage 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: '${prefix}st'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' existing = {
  parent: storage
  name: 'default'
}

resource exports 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobs
  name: 'exports'
}

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2024-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-exports'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: { blobTypes: ['blockBlob'], prefixMatch: ['exports/'] }
            actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: 7 } } }
          }
        }
      ]
    }
  }
}

// --- Key Vault and the workload identity ------------------------------------------

resource kv 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: '${prefix}-kv'
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    softDeleteRetentionInDays: 7
  }
}

resource workload 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'hitc-workload'
  location: location
}

resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: workload
  name: 'hitc-k8s'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:hitc:hitc'
    audiences: ['api://AzureADTokenExchange']
  }
}

// --- Alerts -----------------------------------------------------------------------

resource oncall 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'hitc-oncall'
  location: 'global'
  properties: {
    groupShortName: 'hitconcall'
    enabled: true
    emailReceivers: [{ name: 'oncall', emailAddress: alertEmail }]
  }
}

var alerts = [
  {
    name: 'hitc-dead-letters'
    scope: bus.id
    metric: 'DeadletteredMessages'
    aggregation: 'Maximum'
    threshold: 0
    description: 'A job failed five times and was dead-lettered'
  }
  {
    name: 'hitc-queue-backlog'
    scope: bus.id
    metric: 'ActiveMessages'
    aggregation: 'Average'
    threshold: 50
    description: 'Workers are not keeping up with the job queue'
  }
  {
    name: 'hitc-db-storage'
    scope: pg.id
    metric: 'storage_percent'
    aggregation: 'Average'
    threshold: 80
    description: 'PostgreSQL storage above 80 percent'
  }
  {
    name: 'hitc-node-cpu'
    scope: aks.id
    metric: 'node_cpu_usage_percentage'
    aggregation: 'Average'
    threshold: 80
    description: 'AKS nodes above 80 percent CPU; the autoscaler should be adding a node'
  }
]

resource metricAlerts 'Microsoft.Insights/metricAlerts@2018-03-01' = [for a in alerts: {
  name: a.name
  location: 'global'
  properties: {
    description: a.description
    severity: 2
    enabled: true
    scopes: [a.scope]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'cond0'
          metricName: a.metric
          operator: 'GreaterThan'
          threshold: a.threshold
          timeAggregation: a.aggregation
        }
      ]
    }
    actions: [{ actionGroupId: oncall.id }]
  }
}]

output acrLoginServer string = acr.properties.loginServer
output postgresHost string = pg.properties.fullyQualifiedDomainName
output oidcIssuer string = aks.properties.oidcIssuerProfile.issuerURL
