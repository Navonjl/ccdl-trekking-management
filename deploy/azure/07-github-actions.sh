#!/usr/bin/env bash
# Step 7: let GitHub Actions deploy without a stored password. A managed
# identity trusts OIDC tokens that GitHub issues to this repo's production
# environment, which only the deploy job on main uses. It holds only what a
# release needs: push to the registry, fetch cluster credentials, and upload
# the front end. The workflow is .github/workflows/deploy.yml.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/07-github-actions.log"
: > "$LOG"
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
GH_IDENTITY=hitc-github

missing az identity show -g "$RG" -n "$GH_IDENTITY" &&
  run az identity create --resource-group "$RG" --name "$GH_IDENTITY" --location "$LOCATION" -o table
PRINCIPAL=$(az identity show -g "$RG" -n "$GH_IDENTITY" --query principalId -o tsv)
CLIENT_ID=$(az identity show -g "$RG" -n "$GH_IDENTITY" --query clientId -o tsv)

# GitHub's OIDC subject uses immutable IDs next to the names, so renaming the
# owner or the repo cannot hand the identity to someone else.
OWNER_ID=$(gh api "repos/$REPO" --jq .owner.id)
REPO_ID=$(gh api "repos/$REPO" --jq .id)
SUBJECT="repo:${REPO%%/*}@$OWNER_ID/${REPO#*/}@$REPO_ID:environment:production"
run az identity federated-credential create --resource-group "$RG" --identity-name "$GH_IDENTITY" \
  --name github-production --issuer https://token.actions.githubusercontent.com \
  --subject "$SUBJECT" --audiences api://AzureADTokenExchange -o table

grant() {
  run az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role "$1" --scope "$2" -o none
}
grant AcrPush "$(az acr show -n "$ACR" --query id -o tsv)"
grant "Azure Kubernetes Service Cluster User Role" "$(az aks show -g "$RG" -n "$AKS" --query id -o tsv)"
grant "Storage Blob Data Contributor" "$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)"

# Identifiers, not secrets: they say which identity to sign in as, and only
# a token for this repo's production environment can use them.
run gh variable set AZURE_CLIENT_ID --body "$CLIENT_ID"
run gh variable set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
run gh variable set AZURE_SUBSCRIPTION_ID --body "$(az account show --query id -o tsv)"
run gh variable list
