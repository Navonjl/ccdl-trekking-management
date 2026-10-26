#!/usr/bin/env bash
# Step 3: build the image and push it to ACR, publish the Vue build to Blob
# Storage, and install the Helm chart on AKS.
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/03-deploy.log"
: > "$LOG"
ROOT="$HERE/../.."
TAG="$(git -C "$ROOT" rev-parse --short HEAD)-$(date +%Y%m%d%H%M)"

# --- Image ----------------------------------------------------------------------
push_image "$TAG"
run az acr repository show-tags --name "$ACR" --repository hitc-api --orderby time_desc --top 3 -o table

# --- Front end: static files in the $web container ---------------------------
(cd "$ROOT/frontend" && npm ci --silent && npm run build --silent)
export AZURE_STORAGE_ACCOUNT="$STORAGE"
AZURE_STORAGE_KEY=$(az storage account keys list -g "$RG" -n "$STORAGE" --query '[0].value' -o tsv)
export AZURE_STORAGE_KEY
run az storage blob upload-batch --destination '$web' --source "$ROOT/frontend/dist" \
  --overwrite --only-show-errors -o none
run az storage blob list --container-name '$web' --query '[].{name:name, size:properties.contentLength}' -o table

# --- Cluster ----------------------------------------------------------------
run az aks get-credentials --resource-group "$RG" --name "$AKS" --overwrite-existing
run kubectl get nodes -o wide

kubectl create namespace "$K8S_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

run helm upgrade --install hitc "$HERE/../helm/hitc" --namespace "$K8S_NAMESPACE" \
  --set image.repository="$ACR.azurecr.io/hitc-api" --set image.tag="$TAG" \
  --set azure.tenantId="$(az account show --query tenantId -o tsv)" \
  --set azure.workloadClientId="$WORKLOAD_CLIENT_ID" \
  --set azure.keyVaultName="$KV" \
  --set azure.exportBlobAccountUrl="https://$STORAGE.blob.core.windows.net/" \
  --wait --timeout 10m

run kubectl -n "$K8S_NAMESPACE" get deploy,pods,svc,hpa,scaledobject,pdb
# The API has no public address yet; 04-edge.sh adds the ingress. Check it
# from inside a pod instead.
run kubectl -n "$K8S_NAMESPACE" exec deploy/trek-api -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
