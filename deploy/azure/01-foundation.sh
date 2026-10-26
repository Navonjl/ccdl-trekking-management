#!/usr/bin/env bash
# Step 1: resource group, network, registry, log workspace, then the two slow
# resources (AKS and PostgreSQL) started side by side.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/01-foundation.log"
: > "$LOG"
JOBS=()

run az account show --query '{subscription:name, tenant:tenantDisplayName, user:user.name}' -o table

run az group create --name "$RG" --location "$LOCATION" \
  --tags project=head-in-the-clouds course=CCDL -o table

missing az network vnet show -g "$RG" -n "$VNET" &&
  run az network vnet create --resource-group "$RG" --name "$VNET" \
  --address-prefix 10.20.0.0/16 --subnet-name aks --subnet-prefixes 10.20.0.0/22 -o table

missing az network vnet subnet show -g "$RG" --vnet-name "$VNET" -n postgres &&
  run az network vnet subnet create --resource-group "$RG" --vnet-name "$VNET" \
  --name postgres --address-prefixes 10.20.8.0/24 \
  --delegations Microsoft.DBforPostgreSQL/flexibleServers -o table

missing az acr show -n "$ACR" &&
  run az acr create --resource-group "$RG" --name "$ACR" --sku Basic -o table

# Daily cap of 0.15 GB keeps ingestion inside the free 5 GB a month.
missing az monitor log-analytics workspace show -g "$RG" -n "$LOGS" &&
  run az monitor log-analytics workspace create --resource-group "$RG" \
    --workspace-name "$LOGS" --retention-time 30 --quota 0.15 -o table

# A new workspace takes a few minutes to create its Container Insights tables,
# and AKS refuses to attach monitoring until they exist.
until [[ -n "$(az monitor log-analytics workspace table show -g "$RG" --workspace-name "$LOGS" \
    -n KubePodInventory --query name -o tsv 2>/dev/null)" ]]; do
  echo "  (waiting for the Log Analytics tables)"
  sleep 20
done

AKS_SUBNET_ID=$(az network vnet subnet show -g "$RG" --vnet-name "$VNET" -n aks --query id -o tsv)
LOGS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LOGS" --query id -o tsv)

# AKS: one Burstable node that the cluster autoscaler may grow to two, Azure
# CNI overlay inside our VNet, workload identity, KEDA, Container Insights and
# the Key Vault CSI driver. No SSH key: nothing should ever log in to a node.
# Started as a background job so PostgreSQL and Redis build alongside; the CLI
# refuses --no-wait when it also has to grant the cluster pull access to ACR.
if missing az aks show -g "$RG" -n "$AKS"; then
run az aks create --resource-group "$RG" --name "$AKS" --location "$LOCATION" \
  --tier free --node-vm-size "$AKS_VM_SIZE" --node-count 1 \
  --enable-cluster-autoscaler --min-count 1 --max-count 2 \
  --network-plugin azure --network-plugin-mode overlay --vnet-subnet-id "$AKS_SUBNET_ID" \
  --enable-oidc-issuer --enable-workload-identity --enable-keda \
  --enable-addons monitoring,azure-keyvault-secrets-provider --enable-secret-rotation \
  --workspace-resource-id "$LOGS_ID" --attach-acr "$ACR" \
  --no-ssh-key -o none &
JOBS+=($!)
fi

# PostgreSQL 17, private access only: it gets an address in the delegated
# subnet and a private DNS zone, and is unreachable from the internet.
if [[ -z "${PG_PASSWORD:-}" ]]; then
  remember PG_PASSWORD "$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 28)"
fi
# The private DNS zone the server registers itself in, linked to the VNet so
# pods resolve the server's name to its private address.
PG_ZONE=hitcdb.private.postgres.database.azure.com
missing az network private-dns zone show -g "$RG" -n "$PG_ZONE" &&
  run az network private-dns zone create --resource-group "$RG" --name "$PG_ZONE" -o table
missing az network private-dns link vnet show -g "$RG" -z "$PG_ZONE" -n hitc-vnet-link &&
  run az network private-dns link vnet create --resource-group "$RG" --zone-name "$PG_ZONE" \
    --name hitc-vnet-link --virtual-network "$VNET" --registration-enabled false -o table
PG_ZONE_ID=$(az network private-dns zone show -g "$RG" -n "$PG_ZONE" --query id -o tsv)

if missing az postgres flexible-server show -g "$RG" -n "$PG"; then
run az postgres flexible-server create --resource-group "$RG" --name "$PG" \
  --location "$LOCATION" --version 17 --tier Burstable --sku-name Standard_B1ms \
  --storage-size 32 --backup-retention 7 \
  --vnet "$VNET" --subnet postgres --private-dns-zone "$PG_ZONE_ID" \
  --admin-user "$PG_ADMIN" --admin-password "$PG_PASSWORD" \
  --yes -o none &
JOBS+=($!)
fi

for job in "${JOBS[@]}"; do wait "$job"; done

missing az postgres flexible-server db show -g "$RG" -s "$PG" -n "$PG_DB" &&
  run az postgres flexible-server db create --resource-group "$RG" \
    --server-name "$PG" --name "$PG_DB" -o table
run az postgres flexible-server show --resource-group "$RG" --name "$PG" \
  --query '{name:name, version:version, sku:sku.name, state:state, fqdn:fullyQualifiedDomainName, publicAccess:network.publicNetworkAccess}' -o table

run az aks wait --resource-group "$RG" --name "$AKS" --created --interval 30 --timeout 1800
run az aks show --resource-group "$RG" --name "$AKS" \
  --query '{name:name, k8s:kubernetesVersion, state:provisioningState, nodes:agentPoolProfiles[0].count, size:agentPoolProfiles[0].vmSize, oidcIssuer:oidcIssuerProfile.issuerUrl}' -o table
