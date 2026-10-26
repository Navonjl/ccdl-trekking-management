#!/usr/bin/env bash
# Step 5: the Function app that replaces Celery beat, then alerts and a budget.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/05-jobs-and-monitoring.log"
: > "$LOG"

# --- Timer triggers on Azure Functions (Flex Consumption) ---------------------
missing az functionapp show -g "$RG" -n "$FUNC" &&
  run az functionapp create --resource-group "$RG" --name "$FUNC" \
    --storage-account "$STORAGE" --flexconsumption-location "$LOCATION" \
    --runtime python --runtime-version 3.13 --instance-memory 512 \
    --maximum-instance-count 40 --assign-identity '[system]' -o none

# The broker URL comes from Key Vault through a Key Vault reference, read with
# the Function app's own managed identity.
FUNC_PRINCIPAL=$(az functionapp identity show -g "$RG" -n "$FUNC" --query principalId -o tsv)
KV_ID=$(az keyvault show -g "$RG" -n "$KV" --query id -o tsv)
run az role assignment create --assignee-object-id "$FUNC_PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" --query '{role:roleDefinitionName, scope:scope}' -o table
run az functionapp config appsettings set --resource-group "$RG" --name "$FUNC" \
  --settings "CELERY_BROKER_URL=@Microsoft.KeyVault(VaultName=$KV;SecretName=celery-broker-url)" \
  --query '[?name==`CELERY_BROKER_URL`].{name:name, value:value}' -o table

ZIP="$HERE/logs/functions.zip"
rm -f "$ZIP"
(cd "$HERE/../../functions" && zip -q -r "$ZIP" function_app.py host.json requirements.txt)
run az functionapp deployment source config-zip --resource-group "$RG" --name "$FUNC" \
  --src "$ZIP" --build-remote true -o none
run az functionapp function list --resource-group "$RG" --name "$FUNC" \
  --query '[].{name:name, trigger:config.bindings[0].type, schedule:config.bindings[0].schedule}' -o table

# --- Alerts -----------------------------------------------------------------
ALERT_EMAIL=$(az account show --query user.name -o tsv)
missing az monitor action-group show -g "$RG" -n hitc-oncall &&
  run az monitor action-group create --resource-group "$RG" --name hitc-oncall \
    --short-name hitconcall --action email oncall "$ALERT_EMAIL" -o none
AG_ID=$(az monitor action-group show -g "$RG" -n hitc-oncall --query id -o tsv)

SB_ID=$(az servicebus namespace show -g "$RG" -n "$SB" --query id -o tsv)
PG_ID=$(az postgres flexible-server show -g "$RG" -n "$PG" --query id -o tsv)
AKS_ID=$(az aks show -g "$RG" -n "$AKS" --query id -o tsv)

alert() {
  local name="$1" scope="$2" condition="$3" description="$4"
  missing az monitor metrics alert show -g "$RG" -n "$name" &&
    run az monitor metrics alert create --resource-group "$RG" --name "$name" \
      --scopes "$scope" --condition "$condition" --window-size 5m --evaluation-frequency 5m \
      --severity 2 --action "$AG_ID" --description "$description" -o none
  return 0
}
alert hitc-dead-letters "$SB_ID" "max DeadletteredMessages > 0" \
  "A job failed five times and was dead-lettered"
alert hitc-queue-backlog "$SB_ID" "avg ActiveMessages > 50" \
  "Workers are not keeping up with the job queue"
alert hitc-db-storage "$PG_ID" "avg storage_percent > 80" \
  "PostgreSQL storage above 80 percent"
alert hitc-node-cpu "$AKS_ID" "avg node_cpu_usage_percentage > 80" \
  "AKS nodes above 80 percent CPU; the autoscaler should be adding a node"

run az monitor metrics alert list --resource-group "$RG" \
  --query '[].{name:name, severity:severity, enabled:enabled, description:description}' -o table

# --- Budget: e-mail at 80 percent of 20 USD a month ------------------------------
# Some student offers do not support budgets through the API; that is not fatal.
run az consumption budget create --budget-name hitc-monthly --amount 20 \
  --category cost --time-grain monthly \
  --start-date "$(date +%Y-%m-01)" --end-date 2027-06-30 -o none ||
  echo "budget not supported on this subscription offer; skipped" | tee -a "$LOG"
