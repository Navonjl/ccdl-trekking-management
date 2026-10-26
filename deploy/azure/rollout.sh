#!/usr/bin/env bash
# Ship a code change to the running deployment, in well under five minutes.
#
#   - Podman's layer cache means a code-only change rebuilds and pushes one
#     small layer; the dependency layer is reused until uv.lock changes
#   - the front end is rebuilt and uploaded only when frontend/ changed, in
#     parallel with the image build
#   - Helm rolls the API one pod at a time behind its readiness probe, so the
#     site stays up throughout
source "$(dirname "$0")/config.sh"
LOG="$HERE/logs/rollout.log"
: > "$LOG"
ROOT="$HERE/../.."
STARTED=$(date +%s)
# mark NAME: log how many seconds into the rollout a phase finished.
mark() {
  printf '[%4ss] %s\n' "$(( $(date +%s) - STARTED ))" "$1" | tee -a "$LOG"
}
TAG="$(git -C "$ROOT" rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)"

# --- Front end, in the background -------------------------------------------
FRONTEND_HASH=$(cd "$ROOT/frontend" && git ls-files -co --exclude-standard src public index.html package-lock.json vite.config.js \
  | sort | xargs sha256sum | sha256sum | cut -c1-16)
if [[ "$FRONTEND_HASH" != "${DEPLOYED_FRONTEND:-}" ]]; then
  (
    cd "$ROOT/frontend" && npm ci --silent && npm run build --silent
    AZURE_STORAGE_KEY=$(az storage account keys list -g "$RG" -n "$STORAGE" --query '[0].value' -o tsv)
    AZURE_STORAGE_ACCOUNT="$STORAGE" AZURE_STORAGE_KEY="$AZURE_STORAGE_KEY" \
      az storage blob upload-batch --destination '$web' --source dist --overwrite --only-show-errors -o none
  ) > "$HERE/logs/rollout-frontend.log" 2>&1 &
  FRONTEND_JOB=$!
  echo "front end changed; rebuilding in the background" | tee -a "$LOG"
else
  echo "front end unchanged; skipped" | tee -a "$LOG"
fi

# --- Image ----------------------------------------------------------------------
push_image "$TAG"

# --- Release ------------------------------------------------------------------
run helm upgrade hitc "$HERE/../helm/hitc" --namespace "$K8S_NAMESPACE" \
  --reuse-values --set image.tag="$TAG" --wait --timeout 4m
mark "helm upgrade done"
run kubectl -n "$K8S_NAMESPACE" rollout status deploy/trek-api --timeout 60s
mark "api pods replaced"

if [[ -n "${FRONTEND_JOB:-}" ]]; then
  wait "$FRONTEND_JOB" && remember DEPLOYED_FRONTEND "$FRONTEND_HASH"
  mark "front end uploaded"
fi

run curl -sS --fail "https://$SITE_HOST/api/health"
echo
mark "healthy through the public address"
printf '\nrollout of %s finished in %ss\n' "$TAG" "$(( $(date +%s) - STARTED ))" | tee -a "$LOG"
