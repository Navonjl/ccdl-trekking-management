#!/usr/bin/env bash
# Step 6: the same infrastructure as Bicep (deploy/bicep/main.bicep), checked
# against what the scripts built. what-if reports the difference between the
# template and the live resource group without changing anything.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/06-bicep-what-if.log"
: > "$LOG"
BICEP="$HERE/../bicep/main.bicep"

run az bicep version
run az bicep build --file "$BICEP" --outfile "$HERE/logs/main.json"

PARAMS=(pgAdminPassword="$PG_PASSWORD" alertEmail="$(az account show --query user.name -o tsv)")

run az deployment group validate --resource-group "$RG" --template-file "$BICEP" \
  --parameters "${PARAMS[@]}" --query properties.provisioningState -o tsv

run az deployment group what-if --resource-group "$RG" --template-file "$BICEP" \
  --parameters "${PARAMS[@]}" --result-format ResourceIdOnly --no-pretty-print \
  --query 'changes[].{change:changeType, resource:resourceId}' -o table

# The detailed diff, for anything what-if reports as Modify.
run az deployment group what-if --resource-group "$RG" --template-file "$BICEP" \
  --parameters "${PARAMS[@]}" --exclude-change-types NoChange Ignore
