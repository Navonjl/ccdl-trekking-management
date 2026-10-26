# Names and sizes shared by every script in deploy/azure. Sourced, not run.
#
# Sized for an Azure for Students subscription. Every piece is an Azure
# service, on its free tier where Azure has one: AKS's free control plane and
# its application routing add-on, PostgreSQL B1ms from the 12-month free
# services, Functions Flex Consumption and Log Analytics inside their monthly
# free grants. Managed Redis and the AKS node have no free tier and use their
# smallest sizes. Student subscriptions cannot create Front Door or use ACR
# Tasks, so the edge is the add-on's NGINX and images are built locally.

set -euo pipefail

LOCATION=centralindia
RG=hitc-rg
PREFIX=hitc602                  # globally unique names hang off this

VNET=hitc-vnet
ACR="${PREFIX}acr"
LOGS=hitc-logs
AKS=hitc-aks
AKS_VM_SIZE=Standard_B2s_v2
PG="${PREFIX}-pg"
PG_ADMIN=hitcadmin
PG_DB=hitc
REDIS="${PREFIX}-redis"
SB="${PREFIX}bus"
SB_QUEUE=celery
STORAGE="${PREFIX}st"
KV="${PREFIX}-kv"
IDENTITY=hitc-workload
FUNC="${PREFIX}-func"
FD="${PREFIX}-fd"
FD_ENDPOINT="${PREFIX}"
WAF=hitc602waf

K8S_NAMESPACE=hitc
K8S_SA=hitc
SITE_DNS_LABEL="${PREFIX}"
SITE_HOST="$SITE_DNS_LABEL.$LOCATION.cloudapp.azure.com"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$HERE/.state.env"        # generated passwords and keys; gitignored
mkdir -p "$HERE/logs"
# Cluster credentials stay in the project instead of ~/.kube/config.
export KUBECONFIG="$HERE/.kubeconfig"
touch "$STATE"
# shellcheck disable=SC1090
source "$STATE"

# run CMD...: print the command, run it, and append both to the step's log, so
# the lab report can quote exactly what was typed and what Azure answered.
# Generated secrets are replaced by <redacted> on the way into the log.
run() {
  printf '\n$ %s\n' "$*" | mask | tee -a "$LOG"
  "$@" 2>&1 | mask | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

mask() {
  local line key value
  while IFS= read -r line; do
    while IFS='=' read -r key _; do
      [[ -n "$key" ]] || continue
      value="${!key:-}"
      [[ ${#value} -ge 8 ]] && line="${line//"$value"/<redacted>}"
    done < "$STATE"
    printf '%s\n' "$line"
  done
}

# missing CMD...: true when an `az ... show` for the resource fails, so a step
# that already succeeded is skipped when a script is re-run.
missing() {
  ! "$@" >/dev/null 2>&1
}

# push_image TAG: build the image with Podman and push it to ACR. ACR Tasks
# (az acr build) is not allowed on Azure for Students subscriptions, and a
# local build keeps its layer cache, so a code-only change rebuilds and pushes
# one small layer. The registry token comes from az and never reaches the log.
push_image() {
  local tag="$1" registry="$ACR.azurecr.io"
  az acr login --name "$ACR" --expose-token --query accessToken -o tsv |
    podman login "$registry" --username 00000000-0000-0000-0000-000000000000 --password-stdin >/dev/null
  run podman build --quiet --platform linux/amd64 \
    -t "$registry/hitc-api:$tag" -t "$registry/hitc-api:latest" "$HERE/../.."
  if declare -F mark >/dev/null; then mark "image built"; fi
  run podman push --quiet "$registry/hitc-api:$tag"
  run podman push --quiet "$registry/hitc-api:latest"
  if declare -F mark >/dev/null; then mark "image pushed"; fi
}

# remember KEY VALUE: keep a generated value for later scripts.
remember() {
  sed -i "/^$1=/d" "$STATE"
  printf '%s=%q\n' "$1" "$2" >> "$STATE"
  export "$1=$2"
}
