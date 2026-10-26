#!/usr/bin/env bash
# Step 2: Azure Managed Redis, Service Bus, Blob Storage, Key Vault, the
# workload identity and its federation with the cluster, and the secrets the
# pods will read.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/02-services.log"
: > "$LOG"

# Retry a command while a fresh role assignment propagates (up to ~5 min).
retry() {
  local i
  for i in $(seq 1 15); do
    "$@" && return 0
    echo "  (waiting for role assignment to propagate, attempt $i)"
    sleep 20
  done
  return 1
}

# --- Azure Managed Redis: response cache and Celery results -----------------
# Smallest Balanced size. The cluster comes first and its single database
# once the cluster is running; Service Bus and Storage build in the meantime.
missing az redisenterprise show -g "$RG" -n "$REDIS" &&
  run az redisenterprise create --resource-group "$RG" --name "$REDIS" \
    --location "$LOCATION" --sku Balanced_B0 --public-network-access Enabled \
    --no-database --no-wait

# --- Service Bus: the Celery broker -----------------------------------------
missing az servicebus namespace show -g "$RG" -n "$SB" &&
  run az servicebus namespace create --resource-group "$RG" --name "$SB" \
    --location "$LOCATION" --sku Basic -o table

# Five delivery attempts, then the message moves to the dead-letter subqueue.
missing az servicebus queue show -g "$RG" --namespace-name "$SB" -n "$SB_QUEUE" &&
  run az servicebus queue create --resource-group "$RG" --namespace-name "$SB" \
    --name "$SB_QUEUE" --max-delivery-count 5 --lock-duration PT5M \
    --enable-dead-lettering-on-message-expiration true -o table

# --- Storage: the static front end and the CSV exports ----------------------
missing az storage account show -g "$RG" -n "$STORAGE" &&
  run az storage account create --resource-group "$RG" --name "$STORAGE" \
    --location "$LOCATION" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o table

# The az storage data commands below read the key from the environment, so it
# never appears on a command line or in the log.
export AZURE_STORAGE_ACCOUNT="$STORAGE"
AZURE_STORAGE_KEY=$(az storage account keys list -g "$RG" -n "$STORAGE" --query '[0].value' -o tsv)
export AZURE_STORAGE_KEY

run az storage blob service-properties update --static-website \
  --index-document index.html --404-document index.html \
  --query staticWebsite -o table
run az storage container create --name exports -o table

# Exports are throwaway: delete them a week after they are written.
cat > "$HERE/logs/exports-lifecycle.json" <<'EOF'
{
  "rules": [{
    "name": "expire-exports",
    "enabled": true,
    "type": "Lifecycle",
    "definition": {
      "filters": {"blobTypes": ["blockBlob"], "prefixMatch": ["exports/"]},
      "actions": {"baseBlob": {"delete": {"daysAfterModificationGreaterThan": 7}}}
    }
  }]
}
EOF
run az storage account management-policy create --resource-group "$RG" \
  --account-name "$STORAGE" --policy "@$HERE/logs/exports-lifecycle.json" -o none

# --- Key Vault, with RBAC instead of access policies -------------------------
missing az keyvault show -g "$RG" -n "$KV" &&
  run az keyvault create --resource-group "$RG" --name "$KV" --location "$LOCATION" \
    --enable-rbac-authorization true --retention-days 7 -o table

KV_ID=$(az keyvault show -g "$RG" -n "$KV" --query id -o tsv)
STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)

run az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Key Vault Secrets Officer" --scope "$KV_ID" --query '{role:roleDefinitionName, scope:scope}' -o table

# --- Workload identity: what the pods authenticate as ------------------------
missing az identity show -g "$RG" -n "$IDENTITY" &&
  run az identity create --resource-group "$RG" --name "$IDENTITY" --location "$LOCATION" -o table

ID_PRINCIPAL=$(az identity show -g "$RG" -n "$IDENTITY" --query principalId -o tsv)
remember WORKLOAD_CLIENT_ID "$(az identity show -g "$RG" -n "$IDENTITY" --query clientId -o tsv)"

run az role assignment create --assignee-object-id "$ID_PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" --query '{role:roleDefinitionName, scope:scope}' -o table
run az role assignment create --assignee-object-id "$ID_PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" --scope "$STORAGE_ID" --query '{role:roleDefinitionName, scope:scope}' -o table

# Trust tokens that the cluster's OIDC issuer mints for the hitc service account.
OIDC_ISSUER=$(az aks show -g "$RG" -n "$AKS" --query oidcIssuerProfile.issuerUrl -o tsv)
missing az identity federated-credential show -g "$RG" --identity-name "$IDENTITY" -n hitc-k8s &&
  run az identity federated-credential create --resource-group "$RG" --identity-name "$IDENTITY" \
    --name hitc-k8s --issuer "$OIDC_ISSUER" \
    --subject "system:serviceaccount:$K8S_NAMESPACE:$K8S_SA" \
    --audiences api://AzureADTokenExchange -o table

# --- Redis database, now that the cluster has had time to come up -----------
# `az redisenterprise wait --custom` never matches here, so poll show instead.
until [[ "$(az redisenterprise show -g "$RG" -n "$REDIS" --query resourceState -o tsv)" == Running ]]; do
  echo "  (waiting for the Redis cluster to come up)"
  sleep 30
done
missing az redisenterprise database show -g "$RG" --cluster-name "$REDIS" &&
  run az redisenterprise database create --resource-group "$RG" --cluster-name "$REDIS" \
    --client-protocol Encrypted --port 10000 --clustering-policy EnterpriseCluster \
    --eviction-policy VolatileLRU --access-keys-auth Enabled -o table

# --- Secrets ----------------------------------------------------------------
PG_FQDN=$(az postgres flexible-server show -g "$RG" -n "$PG" --query fullyQualifiedDomainName -o tsv)
REDIS_HOST=$(az redisenterprise show -g "$RG" -n "$REDIS" --query hostName -o tsv)
remember REDIS_KEY "$(az redisenterprise database list-keys -g "$RG" --cluster-name "$REDIS" --query primaryKey -o tsv)"
remember SB_KEY "$(az servicebus namespace authorization-rule keys list -g "$RG" --namespace-name "$SB" \
  -n RootManageSharedAccessKey --query primaryKey -o tsv)"
remember SB_CONNECTION "$(az servicebus namespace authorization-rule keys list -g "$RG" --namespace-name "$SB" \
  -n RootManageSharedAccessKey --query primaryConnectionString -o tsv)"
[[ -n "${SECRET_KEY:-}" ]] || remember SECRET_KEY "$(openssl rand -hex 32)"
[[ -n "${SECURITY_PASSWORD_SALT:-}" ]] || remember SECURITY_PASSWORD_SALT "$(openssl rand -hex 16)"
[[ -n "${ADMIN_PASSWORD:-}" ]] || remember ADMIN_PASSWORD "$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 16)"
GCHAT=$(sed -n 's/^GCHAT_WEBHOOK_URL=//p' "$HERE/../../.env" 2>/dev/null || true)
[[ -n "$GCHAT" ]] && remember GCHAT_WEBHOOK_URL "$GCHAT"

remember DATABASE_URL "postgresql+psycopg://$PG_ADMIN:$PG_PASSWORD@$PG_FQDN:5432/$PG_DB?sslmode=require"
remember REDIS_URL "rediss://:$REDIS_KEY@$REDIS_HOST:10000/0"
remember CELERY_BROKER_URL "azureservicebus://RootManageSharedAccessKey:$SB_KEY@$SB"

set_secret() {
  retry run az keyvault secret set --vault-name "$KV" --name "$1" --value "$2" \
    --query '{name:name, updated:attributes.updated}' -o table
}
set_secret database-url "$DATABASE_URL"
set_secret redis-url "$REDIS_URL"
set_secret celery-broker-url "$CELERY_BROKER_URL"
set_secret servicebus-connection "$SB_CONNECTION"
set_secret secret-key "$SECRET_KEY"
set_secret security-password-salt "$SECURITY_PASSWORD_SALT"
set_secret admin-password "$ADMIN_PASSWORD"
# Key Vault rejects an empty value; "off" leaves the reminder job on e-mail.
set_secret gchat-webhook-url "${GCHAT_WEBHOOK_URL:-off}"

run az keyvault secret list --vault-name "$KV" --query '[].{name:name, enabled:attributes.enabled}' -o table
