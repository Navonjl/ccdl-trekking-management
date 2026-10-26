#!/usr/bin/env bash
# Terminal captures for Chapter 3. Each one shows the command as typed
# (wrapped for the page) above the real output of running it.
#   docs/report/measure/captures.sh [name ...]
set -uo pipefail
cd "$(dirname "$0")/../../.."
export KUBECONFIG="$PWD/deploy/azure/.kubeconfig"
FIGS=docs/report/figures

cap() {  # cap NAME DISPLAYED-COMMAND REAL-COMMAND
  [[ $# -gt 3 || -z "${ONLY:-}" || " $ONLY " == *" $1 "* ]] || return 0
  { printf '%s\n' "$2"; eval "$3" 2>&1 | grep -v '^WARNING'; } |
    mise exec -- freeze -o "$FIGS/$1.png" --language txt --window --padding 22 --margin 0 \
      --font.size 13 --line-height 1.25 --theme github --border.radius 8 \
      --background "#ffffff" >/dev/null 2>&1
  echo "$1"
}

cap term-resources '$ az resource list -g hitc-rg \
    --query "sort_by([].{Name:name, Type:type}, &Type)" -o table' \
  'az resource list -g hitc-rg --query "sort_by([?!contains(type,\`dataCollection\`) && !contains(type,\`serverFarms\`) && !contains(name,\`Smart\`)].{Name:name, Type:type}, &Type)" -o table'

cap term-aks '$ az aks show -g hitc-rg -n hitc-aks --query "{...}" -o table' \
  'az aks show -g hitc-rg -n hitc-aks --query "{Name:name, K8s:kubernetesVersion, State:provisioningState, Nodes:agentPoolProfiles[0].count, Size:agentPoolProfiles[0].vmSize, KEDA:workloadAutoScalerProfile.keda.enabled, WorkloadId:securityProfile.workloadIdentity.enabled, AppRouting:ingressProfile.webAppRouting.enabled}" -o table'

cap term-postgres '$ az postgres flexible-server show -g hitc-rg -n hitc602-pg \
    --query "{...}" -o table' \
  'az postgres flexible-server show -g hitc-rg -n hitc602-pg --query "{Name:name, Version:version, Sku:sku.name, State:state, HA:highAvailability.mode, PublicAccess:network.publicNetworkAccess}" -o table'

cap term-keyvault '$ az keyvault secret list --vault-name hitc602-kv \
    --query "[].{Secret:name, Enabled:attributes.enabled}" -o table' \
  'az keyvault secret list --vault-name hitc602-kv --query "[].{Secret:name, Enabled:attributes.enabled}" -o table'

cap term-functions '$ az functionapp function list -g hitc-rg -n hitc602-func \
    --query "[].{Function:name, Trigger:..., Schedule:...}" -o table' \
  'az functionapp function list -g hitc-rg -n hitc602-func --query "[].{Function:name, Trigger:config.bindings[0].type, Schedule:config.bindings[0].schedule}" -o table'

cap term-alerts '$ az monitor metrics alert list -g hitc-rg \
    --query "[].{Alert:name, Severity:severity, Enabled:enabled}" -o table' \
  'az monitor metrics alert list -g hitc-rg --query "[].{Alert:name, Severity:severity, Enabled:enabled}" -o table'

cap term-acr '$ git log --oneline -4' 'git log --oneline -4'
cap term-acr-tags '$ az acr repository show-tags -n hitc602acr --repository hitc-api \
    --orderby time_desc --top 4 -o table' \
  'az acr repository show-tags -n hitc602acr --repository hitc-api --orderby time_desc --top 4 -o table'

cap term-k8s '$ kubectl -n hitc get deploy,hpa
$ kubectl -n hitc get scaledobject' \
  'kubectl -n hitc get deploy,hpa; echo; kubectl -n hitc get scaledobject -o custom-columns=NAME:.metadata.name,TARGET:.spec.scaleTargetRef.name,MIN:.spec.minReplicaCount,MAX:.spec.maxReplicaCount,TRIGGER:.spec.triggers[0].type,QUEUE:.spec.triggers[0].metadata.queueName,READY:.status.conditions[0].status'

cap term-pods '$ kubectl -n hitc get pods,svc,ingress' \
  'kubectl -n hitc get pods,svc,ingress | grep -v db-init | cut -c1-130'

cap term-tls '$ kubectl -n hitc get certificate
$ curl https://hitc602.centralindia.cloudapp.azure.com/api/health' \
  'kubectl -n hitc get certificate; echo; curl -sS https://hitc602.centralindia.cloudapp.azure.com/api/health; echo'

cap term-helm '$ helm list -A' 'helm list -A | cut -c1-140'

cap term-whatif '$ az deployment group validate -g hitc-rg --template-file deploy/bicep/main.bicep ...
$ az deployment group what-if -g hitc-rg --template-file deploy/bicep/main.bicep ...' \
  'L=deploy/azure/logs/06-bicep-what-if.log
   sed -n "/^\$ az deployment group validate/{n;p}" $L
   echo
   sed -n "/^\$ az deployment group what-if/,/^\$ /p" $L | awk "/^(Deploy|Ignore|Create|Delete|Modify|NoChange) /{c[\$1]++} END {for (k in c) printf \"%-8s %d resources\n\", k, c[k]}" | sort
   echo
   sed -n "/--exclude-change-types/,\$p" $L | grep -E "^  [~+-] Microsoft" | sed -E "s/ \[[0-9-]+\]//"
   grep "^Resource changes" $L | tail -1'

cap term-actions '$ gh run list --workflow deploy.yml --limit 3
$ gh run view 40279943367 --verbose' \
  'gh run list --workflow deploy.yml --limit 3 | cut -f1-2,4,5,7,8 | column -t -s $'"'"'\t'"'"' | cut -c1-120; echo; gh run view 40279943367 --verbose 2>&1 | sed -n "/^JOBS/,/^ANNOTATIONS/p" | grep -v -e ANNOTATIONS -e "Post Run" -e "Set up job" -e "Complete job" -e "^$"'
